"""`spec init`: sets up a repository for the toolkit in one step (SYS-5, CLI-9).

It writes:
- spec/, with a root system element, when the repository has no spec yet;
- .syseng/spec, the launcher agents run the toolkit with. It's committed, and hands over to
  this machine's launcher (DR-39);
- this machine's launcher, ${XDG_CONFIG_HOME:-~/.config}/syseng/launcher, which says which
  Python runs the toolkit. An existing one that works is kept unless --launcher replaces it;
- the skill, for each harness named: .claude/skills/syseng for Claude Code, and .agents/skills/syseng,
  the cross-tool location, for Hermes and Antigravity. Each copy has the launcher's name and a note on
  what that harness's hooks do filled in (DR-38, AGENT-49);
- for Claude Code: .syseng/hook, the hooks that run it in .claude/settings.json, and the auditor
  and reasoning-check subagents in .claude/agents (DR-40).

Running it again refreshes these files and leaves every other setting alone (CLI-10).
"""

import json
import os
import shlex
import stat
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

from syseng import model, render, yamlio

PACKAGE = Path(__file__).resolve().parent
SKILL = PACKAGE / "skill"
ADAPTERS = PACKAGE / "adapters"
SPEC_CMD = ".syseng/spec"
HARNESSES = ("claude-code", "hermes", "antigravity", "none")
SKILL_HOMES = {"claude-code": ".claude/skills/syseng", "hermes": ".agents/skills/syseng",
               "antigravity": ".agents/skills/syseng"}
HARNESS_NOTES = {"claude-code": ADAPTERS / "claude_code" / "skill-notes.md"}  # the others run no hooks
GENERIC_NOTES = ADAPTERS / "generic" / "skill-notes.md"
HOOK_MARK = ".syseng/hook"
HOOKS = {  # event: (matcher, argument to the hook script)
    "PreToolUse": ("Edit|Write|MultiEdit|NotebookEdit|Bash|PowerShell", "pre-tool"),
    "Stop": (None, "stop"),
    "UserPromptSubmit": (None, "prompt"),
}
_LANGUAGES = [("pyproject.toml", "python"), ("setup.py", "python"), ("Cargo.toml", "rust"), ("go.mod", "go"),
              ("CMakeLists.txt", "cpp"), ("tsconfig.json", "typescript"), ("package.json", "javascript")]

REPO_LAUNCHER = """#!/bin/sh
# Runs the spec toolkit for this repository. Written by `spec init`; commit it.
# Which Python runs the toolkit is a per-machine choice, kept in
# ${XDG_CONFIG_HOME:-$HOME/.config}/syseng/launcher, which `spec init` also writes.
machine="${XDG_CONFIG_HOME:-$HOME/.config}/syseng/launcher"
if [ -x "$machine" ]; then
  exec "$machine" "$@"
fi
echo "The spec toolkit is not set up on this machine. Install it with pip, then run 'spec init' in this repository." >&2
exit 127
"""


class InitError(Exception):
    pass


@dataclass
class Step:
    status: str  # created | updated | unchanged | kept | removed | differs
    path: str
    note: str = ""


def machine_launcher_path() -> Path:
    return Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config") / "syseng" / "launcher"


def default_launcher() -> str:
    """The command that runs this toolkit: this Python, plus its source directory when it isn't installed."""
    py = shlex.quote(sys.executable)
    env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
    probe = subprocess.run([sys.executable, "-c", "import syseng; print(syseng.__file__)"], env=env,
                           cwd=tempfile.gettempdir(), capture_output=True, text=True)
    if probe.returncode == 0 and Path(probe.stdout.strip()).resolve().parent == PACKAGE:
        return f"{py} -m syseng"
    src = shlex.quote(str(PACKAGE.parent))
    return f'env PYTHONPATH={src}"${{PYTHONPATH:+:$PYTHONPATH}}" {py} -m syseng'


def machine_launcher_text(command: str) -> str:
    return ("#!/bin/sh\n"
            "# This machine's spec toolkit, which each repository's .syseng/spec runs. Written by `spec init`.\n"
            f'exec {command} "$@"\n')


def _works(launcher: Path) -> bool:
    try:
        return subprocess.run([str(launcher), "--help"], capture_output=True, timeout=60).returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


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


def merge_settings(text: str | None) -> str:
    """Claude Code settings with this toolkit's hooks, replacing older copies and keeping everything else."""
    try:
        data = json.loads(text) if text and text.strip() else {}
    except ValueError as e:
        raise InitError(f"can't read .claude/settings.json ({e}). Fix it, then run `spec init` again.") from e
    if not isinstance(data, dict):
        raise InitError(".claude/settings.json isn't a JSON object. Fix it, then run `spec init` again.")
    hooks = data.setdefault("hooks", {})
    for event, (matcher, arg) in HOOKS.items():
        kept = []
        for group in hooks.get(event) or []:
            inner = [h for h in group.get("hooks") or [] if HOOK_MARK not in str(h.get("command", ""))]
            if inner:
                kept.append({**group, "hooks": inner})
        ours = {"hooks": [{"type": "command", "command": f'"$CLAUDE_PROJECT_DIR"/{HOOK_MARK} {arg}'}]}
        hooks[event] = kept + [{"matcher": matcher, **ours} if matcher else ours]
    return json.dumps(data, indent=2) + "\n"


def planned_files(repo: Path, harnesses: list[str]) -> dict[str, tuple[str, bool]]:
    """Every file `spec init` keeps up to date in the repository: path -> (content, executable)."""
    files = {SPEC_CMD: (REPO_LAUNCHER, True)}
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
    render.write_views(model.load(root))
    return Step("created", "spec/", f"root system element SYS; implementation {language!r}, {how}")


def run(repo: Path, harnesses: list[str], launcher: str | None = None, check_only: bool = False) -> list[Step]:
    """Sets up `repo`, or with check_only reports what differs from a fresh setup without writing."""
    unknown = [h for h in harnesses if h not in HARNESSES]
    if unknown:
        raise InitError(f"unknown harness {', '.join(unknown)}; choose from {', '.join(HARNESSES)}")
    steps: list[Step] = []
    if not check_only:
        steps.append(_skeleton(repo))
    for rel, (content, executable) in planned_files(repo, harnesses).items():
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
    if not check_only:
        steps.append(_machine_launcher(launcher))
    return steps


def _machine_launcher(command: str | None) -> Step:
    path = machine_launcher_path()
    if command is None and path.exists() and _works(path):
        return Step("kept", str(path), "this machine's launcher; --launcher replaces it")
    status = "created" if not path.exists() else "updated"
    command = command or default_launcher()
    _write(path, machine_launcher_text(command), True)
    return Step(status, str(path), "this machine's launcher: " + command)
