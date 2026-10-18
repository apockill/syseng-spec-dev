"""Names the command agents type in a repository, so every message gives a line they can run (CLI-15).

A repository that `spec init` set up runs the toolkit as `.syseng/spec`; anywhere else it's `spec`.
Only text the toolkit writes is named this way, never spec content: the engineer's words stay exact.
"""

from pathlib import Path

_current = "spec"


def command(spec_root: Path) -> str:
    return ".syseng/spec" if (spec_root.resolve().parent / ".syseng" / "spec").is_file() else "spec"


def use(spec_root: Path | None) -> None:
    """Sets the command named by this run's messages, from the repository the run works in."""
    global _current
    _current = command(spec_root) if spec_root is not None else "spec"


def cmd(args: str) -> str:
    """A command, in backticks, as this repository runs it."""
    return f"`{_current} {args}`"


def localize(text: str, spec_root: Path) -> str:
    """Rewrites each `spec …` command in toolkit-authored text, such as a rule's fix."""
    name = command(spec_root)
    return text if name == "spec" else text.replace("`spec ", f"`{name} ")
