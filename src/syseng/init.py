"""`spec init`: sets up a repository for the toolkit in one step.

Agents and hooks run the toolkit as `spec`, from the PATH: install it with `pipx install` or
`uv tool install` (add `--editable` to run a checkout). It writes:
- spec/, with a root system element, when the repository has no spec yet;
- the skill, for each harness named: .claude/skills/syseng for Claude Code, and .agents/skills/syseng,
  the cross-tool location, for Hermes and Antigravity. Each copy has a note on what that harness's
  hooks do filled in;
- for Claude Code: .syseng/hook, the hooks that run it in .claude/settings.json, and the auditor
  and reasoning-check subagents in .claude/agents;
- a short section in AGENTS.md (or CLAUDE.md), between markers, telling every session to follow
  the skill. --no-instructions leaves those files alone.

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
SKILL_HOMES = {"claude-code": ".claude/skills/syseng", "hermes": ".agents/skills/syseng",
               "antigravity": ".agents/skills/syseng"}
HARNESS_NOTES = {"claude-code": ADAPTERS / "claude_code" / "skill-notes.md"}  # the others run no hooks
GENERIC_NOTES = ADAPTERS / "generic" / "skill-notes.md"
HOOK_MARK = ".syseng/hook"
# Toolkit commands agents may run without asking (CLI-20). `approve` and `resolve` record the engineer's
# words, so they stay with the harness's permission prompt: the engineer sees and confirms each one.
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


def _fill(text: str, harness: str | None = None) -> str:
    if "{{HARNESS_NOTES}}" in text:
        notes = HARNESS_NOTES.get(harness, GENERIC_NOTES).read_text().strip()
        text = text.replace("{{HARNESS_NOTES}}", notes)
    return text.replace("{{SPEC}}", SPEC_CMD)


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


def merge_instructions(text: str | None) -> str:
    """The file with the toolkit's section added, or replaced between its markers (CLI-16)."""
    block = f"{INSTRUCTIONS_BEGIN}\n{INSTRUCTIONS}\n{INSTRUCTIONS_END}\n"
    text = text or ""
    start, end = text.find("<!-- syseng:"), text.find(INSTRUCTIONS_END)
    if start != -1 and end > start:
        return text[:start] + block + text[end + len(INSTRUCTIONS_END):].lstrip("\n")
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
            files[name] = (merge_instructions(path.read_text() if path.exists() else None), False)
    for h in harnesses:
        if h in SKILL_HOMES:
            for src in sorted(p for p in SKILL.rglob("*") if p.is_file() and p.suffix == ".md"):
                files[f"{SKILL_HOMES[h]}/{src.relative_to(SKILL).as_posix()}"] = (_fill(src.read_text(), h), False)
    if "claude-code" in harnesses:
        files[HOOK_MARK] = ((ADAPTERS / "hook.py").read_text(), True)
        for src in sorted((ADAPTERS / "claude_code" / "agents").glob("*.md")):
            files[f".claude/agents/{src.name}"] = (_fill(src.read_text()), False)
        settings = repo / ".claude" / "settings.json"
        files[".claude/settings.json"] = (merge_settings(settings.read_text() if settings.exists() else None), False)
    return files


def installed_harnesses(repo: Path) -> list[str]:
    """One harness per installed skill copy (Hermes and Antigravity share theirs)."""
    found: dict[str, str] = {}
    for h, home in SKILL_HOMES.items():
        if (repo / home).is_dir():
            found.setdefault(home, h)
    return list(found.values())


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
        "spec_version": 1,
        "implementations": [{"name": language, "language": language, "root": ".", "primary": True}],
        "element_order": ["SYS"]})
    yamlio.write(root / "elements" / "SYS" / "element.yaml", {
        "id": "SYS", "title": repo.name, "parent": None, "depends_on": [], "purpose": "The whole system."})
    for name in ("needs.yaml", "requirements.yaml"):
        yamlio.write(root / "elements" / "SYS" / name, [])
    for name in ("approvals.yaml", "retired.yaml"):
        yamlio.write(root / name, [])
    return Step("created", "spec/", f"root system element SYS; implementation {language!r}, {how}")


def run(repo: Path, harnesses: list[str], check_only: bool = False, instructions: bool = True) -> list[Step]:
    """Sets up `repo`, or with check_only reports what differs from a fresh setup without writing."""
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
    for h in harnesses:  # files an older skill had and this one doesn't
        home = SKILL_HOMES.get(h)
        planned = set(planned_files(repo, [h]))
        for old in sorted((repo / home).rglob("*.md")) if home and (repo / home).is_dir() else []:
            rel = old.relative_to(repo).as_posix()
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
        spec_root = repo / "spec"
        if (spec_root / "toolkit.yaml").exists():
            render.write_views(model.load(spec_root))
        if shutil.which(SPEC_CMD) is None:
            steps.append(Step("note", "PATH", "`spec` isn't on the PATH, so agents and hooks can't run it: install the "
                                              "toolkit with `pipx install` or `uv tool install`"))
    return steps
