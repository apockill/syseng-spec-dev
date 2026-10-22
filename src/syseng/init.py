"""`spec init`: sets up a repository for the toolkit in one step.

Agents and hooks run the toolkit as `spec`, from the PATH: install it with `pipx install` or
`uv tool install` (add `--editable` to run a checkout).

In the repository, it writes:
- spec/, with a root system element, when the repository has no spec yet;
- for Claude Code: .syseng/hook and the hooks that run it in .claude/settings.json;
- a short section in AGENTS.md (or CLAUDE.md), between markers, telling every session to follow the
  skill and what this repository's hooks do. --no-instructions leaves those files alone.

On this machine, once, it links the user-level folders to the installed toolkit, so every repository
uses the skill and subagents of the toolkit that's installed, and updating the toolkit updates them:
~/.claude/skills/syseng and the two subagents in ~/.claude/agents for Claude Code, and
~/.hermes/skills/syseng for Hermes. Antigravity, with no user-level folder known, gets a copy of the
skill in the repository's .agents/skills/syseng.

It records the harnesses it set up in spec/toolkit.yaml, and a later run without --harness uses them.

Running it again refreshes these files and leaves every other setting alone.
"""

import json
import os
import shutil
import stat
from dataclasses import dataclass
from pathlib import Path

from syseng import model, render, yamlio

PACKAGE = Path(__file__).resolve().parent
SKILL = PACKAGE / "skill"
ADAPTERS = PACKAGE / "adapters"
SPEC_CMD = "spec"
OLD_LAUNCHER = ".syseng/spec"  # what setups before round 15 wrote; removed when found (DR-52)
HARNESSES = ("claude-code", "hermes", "antigravity", "none")
AGENT_DEFINITIONS = ADAPTERS / "claude_code" / "agents"
SKILL_COPY = ".agents/skills/syseng"   # the skill, copied into the repository for Antigravity only
CLAUDE_LINK = ".claude/skills/syseng"  # where setups before round 17 put Claude Code's copy
OLD_AGENTS = (".claude/agents/spec-auditor.md", ".claude/agents/spec-reasoning-check.md")  # same
CLAUDE_NOTES = ADAPTERS / "claude_code" / "instructions.md"
GENERIC_NOTES = ADAPTERS / "generic" / "instructions.md"
HOOK_MARK = ".syseng/hook"
# Toolkit commands agents may run without asking (CLI-20). `lock` and `resolve` record a person's locks and
# decisions, and `migrate` rewrites records, so they stay with the harness's permission prompt.
_EVERYDAY = ("status", "check", "show", "render", "edit", "change", "decide", "propose", "friction")
ALLOWED = [f"Bash(spec {cmd} *)" for cmd in _EVERYDAY]
_OURS = set(ALLOWED) | {f"Bash(.syseng/spec {cmd} *)" for cmd in _EVERYDAY}  # this and earlier setups' rules
HOOKS = [  # (event, matcher, argument to the hook script)
    ("PreToolUse", "Edit|Write|MultiEdit|NotebookEdit|Bash|PowerShell", "pre-tool"),
    # Here rather than in the subagent's own definition, whose hooks Claude Code skips in untrusted folders.
    ("PreToolUse", "Read|Grep|Glob|NotebookRead", "read-guard"),
    ("Stop", None, "stop"),
    ("UserPromptSubmit", None, "prompt"),
]
_LANGUAGES = [("pyproject.toml", "python"), ("setup.py", "python"), ("Cargo.toml", "rust"), ("go.mod", "go"),
              ("CMakeLists.txt", "cpp"), ("tsconfig.json", "typescript"), ("package.json", "javascript")]

INSTRUCTIONS_BEGIN = "<!-- syseng: written by `spec init`, which rewrites everything up to the closing marker -->"
INSTRUCTIONS_END = "<!-- /syseng -->"
INSTRUCTIONS = """## Requirements and design decisions

This repository keeps its needs, requirements, verification items and design decisions in `spec/`, managed
with the syseng toolkit. For every change, follow the `syseng` skill:

- open a change with `spec change start "<what was asked>"`;
- change the spec only with `spec edit`, never by editing files under `spec/`;
- run `spec check` before reporting a change as done.

`spec status` shows what's open and what awaits the engineer."""

class InitError(Exception):
    pass


@dataclass
class Step:
    status: str  # created | updated | unchanged | kept | removed | differs
    path: str
    note: str = ""


def _guess_language(repo: Path) -> tuple[str, str]:
    for marker, language in _LANGUAGES:
        if (repo / marker).exists():
            return language, f"guessed from {marker}"
    return "main", "no build file recognized"


def instruction_files(repo: Path) -> list[str]:
    """The host's instruction files to carry the section: AGENTS.md and CLAUDE.md, unless one includes the other."""
    found = [n for n in ("AGENTS.md", "CLAUDE.md") if (repo / n).exists()]
    if len(found) == 2:
        claude = repo / "CLAUDE.md"
        if claude.is_symlink() or "@AGENTS.md" in claude.read_text():
            found.remove("CLAUDE.md")
    return found or ["AGENTS.md"]


def instructions_for(harnesses: list[str]) -> str:
    """The section's text: the method, then what this repository's hooks do, harness by harness (AGENT-49)."""
    parts = [INSTRUCTIONS]
    if "claude-code" in harnesses:
        parts.append(CLAUDE_NOTES.read_text().strip())
    if any(h not in ("claude-code", "none") for h in harnesses) or "claude-code" not in harnesses:
        parts.append(GENERIC_NOTES.read_text().strip())
    return "\n\n".join(parts)


def merge_instructions(text: str | None, harnesses: list[str] = ("claude-code",)) -> str:
    """The file with the toolkit's section added, or replaced between its markers (CLI-16)."""
    block = f"{INSTRUCTIONS_BEGIN}\n{instructions_for(list(harnesses))}\n{INSTRUCTIONS_END}\n"
    text = text or ""
    start, end = text.find("<!-- syseng:"), text.find(INSTRUCTIONS_END)
    if start != -1 and end > start:
        rest = text[end + len(INSTRUCTIONS_END):].lstrip("\n")  # what follows keeps one blank line before it
        return text[:start] + block + ("\n" + rest if rest else "")
    return (text.rstrip("\n") + "\n\n" if text.strip() else "") + block


def has_instructions(repo: Path) -> bool:
    return any("<!-- syseng:" in (repo / n).read_text() for n in ("AGENTS.md", "CLAUDE.md") if (repo / n).exists())


def merge_settings(text: str | None) -> str:
    """Claude Code settings with this toolkit's hooks, replacing older copies and keeping everything else."""
    try:
        data = json.loads(text) if text and text.strip() else {}
    except ValueError as e:
        raise InitError(f"can't read .claude/settings.json ({e}). Fix it, then run `spec init` again.") from e
    if not isinstance(data, dict):
        raise InitError(".claude/settings.json isn't a JSON object. Fix it, then run `spec init` again.")
    permissions = data.setdefault("permissions", {})
    allow = [r for r in permissions.get("allow") or [] if r not in _OURS]
    permissions["allow"] = allow + ALLOWED
    hooks = data.setdefault("hooks", {})
    for event in dict.fromkeys(e for e, _, _ in HOOKS):
        kept = []
        for group in hooks.get(event) or []:
            inner = [h for h in group.get("hooks") or [] if HOOK_MARK not in str(h.get("command", ""))]
            if inner:
                kept.append({**group, "hooks": inner})
        for e, matcher, arg in HOOKS:
            if e == event:
                ours = {"hooks": [{"type": "command", "command": f'"$CLAUDE_PROJECT_DIR"/{HOOK_MARK} {arg}'}]}
                kept.append({"matcher": matcher, **ours} if matcher else ours)
        hooks[event] = kept
    return json.dumps(data, indent=2) + "\n"


def planned_files(repo: Path, harnesses: list[str], instructions: bool = False) -> dict[str, tuple[str, bool]]:
    """Every file `spec init` keeps up to date in the repository: path -> (content, executable)."""
    files: dict[str, tuple[str, bool]] = {}
    if instructions:
        for name in instruction_files(repo):
            path = repo / name
            files[name] = (merge_instructions(path.read_text() if path.exists() else None, harnesses), False)
    if "antigravity" in harnesses:
        for src in sorted(p for p in SKILL.rglob("*") if p.is_file() and p.suffix == ".md"):
            files[f"{SKILL_COPY}/{src.relative_to(SKILL).as_posix()}"] = (src.read_text(), False)
    if "claude-code" in harnesses:
        files[HOOK_MARK] = ((ADAPTERS / "hook.py").read_text(), True)
        settings = repo / ".claude" / "settings.json"
        files[".claude/settings.json"] = (merge_settings(settings.read_text() if settings.exists() else None), False)
    return files


def claude_home() -> Path:
    return Path(os.environ.get("CLAUDE_CONFIG_DIR") or Path.home() / ".claude")


def hermes_home() -> Path:
    return Path.home() / ".hermes"


NIX_STORE = "/nix/store/"


def profile_roots() -> list[Path]:
    """Where a Nix profile exposes what it installed; each survives `nix profile upgrade`."""
    user = os.environ.get("USER") or Path.home().name
    return [Path.home() / ".nix-profile", Path.home() / ".local/state/nix/profile",
            Path("/etc/profiles/per-user") / user, Path("/run/current-system/sw")]


def stable(target: Path) -> Path:
    """A path to the installed toolkit that outlives an upgrade. A toolkit installed with Nix lives at a store path
    that changes with every version, so the same file is reached through the profile instead, when it's there."""
    text = str(target)
    if not text.startswith(NIX_STORE):
        return target
    inside = Path(*Path(text[len(NIX_STORE):]).parts[1:])  # the path within the package's store directory
    for root in profile_roots():
        candidate = root / inside
        try:
            if candidate.exists() and candidate.resolve() == target.resolve():
                return candidate
        except OSError:
            continue
    return target


def machine_links(harnesses: list[str]) -> dict[Path, Path]:
    """Links in this machine's user-level folders: path -> what it points at in the installed toolkit (CLI-21)."""
    links: dict[Path, Path] = {}
    if "claude-code" in harnesses:
        links[claude_home() / "skills" / "syseng"] = stable(SKILL)
        for src in sorted(AGENT_DEFINITIONS.glob("*.md")):
            links[claude_home() / "agents" / src.name] = stable(src)
    if "hermes" in harnesses and hermes_home().is_dir():
        links[hermes_home() / "skills" / "syseng"] = stable(SKILL)
    return links


def _tilde(path: Path) -> str:
    home = str(Path.home())
    text = str(path)
    return "~" + text[len(home):] if text == home or text.startswith(home + os.sep) else text


def _machine_link(path: Path, target: Path, check_only: bool) -> Step:
    shown = _tilde(path)
    if path.is_symlink() and Path(os.readlink(path)) == target:
        return Step("unchanged", shown)
    if path.exists() and not path.is_symlink():
        return Step("note", shown, "left alone: it isn't a link `spec init` made")
    if check_only:
        return Step("differs", shown, f"should be a link to {_tilde(target)}")
    existed = path.is_symlink()
    if existed:
        path.unlink()
    path.parent.mkdir(parents=True, exist_ok=True)
    os.symlink(target, path, target_is_directory=target.is_dir())
    return Step("updated" if existed else "created", shown, f"a link to {_tilde(target)}")


def _older_installs(repo: Path, harnesses: list[str]) -> list[str]:
    """What setups before round 17 put in the repository and the user-level links now replace."""
    found = []
    for rel in (CLAUDE_LINK, SKILL_COPY):
        path = repo / rel
        if rel == SKILL_COPY and "antigravity" in harnesses:
            continue  # still the copy Antigravity reads
        skill = path / "SKILL.md"
        if path.is_symlink() or (path.is_dir() and skill.is_file() and "name: syseng" in skill.read_text()):
            found.append(rel)
    found += [rel for rel in OLD_AGENTS if (repo / rel).is_file() and "name: spec-" in (repo / rel).read_text()]
    return found


def installed_harnesses(repo: Path) -> list[str]:
    """The harnesses spec/toolkit.yaml records, or, for older setups, those the skill's folders show."""
    config = repo / "spec" / "toolkit.yaml"
    recorded = (yamlio.read(config) or {}).get("harnesses") if config.exists() else None
    if recorded:
        return [h for h in recorded if h in HARNESSES]
    found = []  # setups before round 16 recorded nothing; their copies show the harnesses
    if (repo / CLAUDE_LINK).exists() or (repo / HOOK_MARK).exists():
        found.append("claude-code")
    if (repo / SKILL_COPY).is_dir() and not (repo / CLAUDE_LINK).is_symlink():
        found.append("hermes")
    return found


def _record_harnesses(repo: Path, harnesses: list[str]) -> None:
    config = repo / "spec" / "toolkit.yaml"
    if not config.exists():
        return
    data = yamlio.read(config) or {}
    merged = list(dict.fromkeys([*(data.get("harnesses") or []), *(h for h in harnesses if h != "none")]))
    if merged != data.get("harnesses"):
        data["harnesses"] = merged
        yamlio.write(config, data)


def _write(path: Path, content: str, executable: bool) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    if executable:
        path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def _skeleton(repo: Path) -> Step:
    root = repo / "spec"
    if (root / "toolkit.yaml").exists():
        return Step("kept", "spec/", "already set up")
    language, how = _guess_language(repo)
    yamlio.write(root / "toolkit.yaml", {
        "spec_version": 2,  # intent records and locks from the start (DR-63)
        "implementations": [{"name": language, "language": language, "root": ".", "primary": True}],
        "element_order": ["SYS"],
        "flow_down": "enforced"})  # requirements flow down the system breakdown from the start (DR-58)
    yamlio.write(root / "elements" / "SYS" / "element.yaml", {
        "id": "SYS", "title": repo.name, "parent": None, "depends_on": [], "purpose": "The whole system."})
    for name in ("needs.yaml", "requirements.yaml"):
        yamlio.write(root / "elements" / "SYS" / name, [])
    for name in ("locks.yaml", "retired.yaml"):
        yamlio.write(root / name, [])
    return Step("created", "spec/", f"root system element SYS; implementation {language!r}, {how}")


def run(repo: Path, harnesses: list[str], check_only: bool = False, instructions: bool = True,
        machine: bool = True) -> list[Step]:
    """Sets up `repo` and, with `machine`, this machine's user-level links; with check_only, reports
    what differs from a fresh setup without writing."""
    instructions = has_instructions(repo) if check_only else instructions
    unknown = [h for h in harnesses if h not in HARNESSES]
    if unknown:
        raise InitError(f"unknown harness {', '.join(unknown)}; choose from {', '.join(HARNESSES)}")
    steps: list[Step] = []
    if not check_only:
        steps.append(_skeleton(repo))
    for rel, (content, executable) in planned_files(repo, harnesses, instructions).items():
        path = repo / rel
        current = path.read_text() if path.exists() else None
        if current == content and (not executable or os.access(path, os.X_OK)):
            steps.append(Step("unchanged", rel))
        elif check_only:
            steps.append(Step("differs", rel, "missing" if current is None else "out of date"))
        else:
            _write(path, content, executable)
            steps.append(Step("created" if current is None else "updated", rel))
    for rel in _older_installs(repo, harnesses):
        path = repo / rel
        if not check_only:
            if path.is_symlink() or path.is_file():
                path.unlink()
            else:
                shutil.rmtree(path)
        steps.append(Step("differs" if check_only else "removed", rel, "installed once per machine now"))
        for parent in [] if check_only else (path.parent, path.parent.parent):  # e.g. .agents/skills, .agents
            if parent != repo and parent.is_dir() and not any(parent.iterdir()):
                parent.rmdir()
    if machine:
        steps += [_machine_link(path, target, check_only) for path, target in machine_links(harnesses).items()]
        if "hermes" in harnesses and not hermes_home().is_dir():
            steps.append(Step("note", "~/.hermes", "Hermes isn't set up on this machine, so its skill link wasn't made"))
    planned = set(planned_files(repo, harnesses))
    copy = repo / SKILL_COPY
    for old in sorted(copy.rglob("*.md")) if copy.is_dir() and not copy.is_symlink() else []:
        rel = old.relative_to(repo).as_posix()  # files an older skill had and this one doesn't
        if rel not in planned:
            if not check_only:
                old.unlink()
            steps.append(Step("differs" if check_only else "removed", rel, "no longer part of the skill"))
    old = repo / OLD_LAUNCHER
    if old.is_file() and "Written by `spec init`" in old.read_text():
        if not check_only:
            old.unlink()
        steps.append(Step("differs" if check_only else "removed", OLD_LAUNCHER, "agents now run `spec` from the PATH"))
    if not check_only:
        _record_harnesses(repo, harnesses)
        spec_root = repo / "spec"
        if (spec_root / "toolkit.yaml").exists():
            render.write_views(model.load(spec_root))
        if shutil.which(SPEC_CMD) is None:
            steps.append(Step("note", "PATH", "`spec` isn't on the PATH, so agents and hooks can't run it: install the "
                                              "toolkit with `pipx install` or `uv tool install`"))
    return steps
