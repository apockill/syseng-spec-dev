"""Which paths a spec covers (SYS-62). A repository may list paths its spec leaves out in `.specignore` at its top,
one pattern per line, in the style git uses for files it ignores: `desklab/`, `*.log`, `# a comment`. Work that touches only those
paths needs no spec.

What's left must each be covered by some element's `related_code`, or the checker lists it as a to-do. Without a
`.specignore`, the spec is taken to cover the whole repository, and nothing is listed.
"""

import fnmatch
from pathlib import Path

FILE = ".specignore"
ALWAYS_OUT = (".git/", ".syseng/", ".claude/", ".agents/", "spec/")  # the toolkit's own files, and version control's


def patterns(repo: Path) -> list[str] | None:
    """The repository's patterns, or None when it has no `.specignore`."""
    path = repo / FILE
    if not path.is_file():
        return None
    return [line.strip() for line in path.read_text().splitlines() if line.strip() and not line.startswith("#")]


def _matches(path: str, pattern: str) -> bool:
    if pattern.endswith("/"):
        folder = pattern.rstrip("/")
        return path == folder or path.startswith(folder + "/") or fnmatch.fnmatch(path.split("/")[0], folder)
    name = pattern.lstrip("/")
    return fnmatch.fnmatch(path, name) or fnmatch.fnmatch(path.rsplit("/", 1)[-1], name) or path.startswith(name + "/")


def ignored(repo: Path, path: str, found: list[str] | None = None) -> bool:
    """Whether a repository-relative path is outside the spec (CHECK-37)."""
    found = patterns(repo) if found is None else found
    return bool(found) and any(_matches(path, p) for p in found)


def uncovered(spec, files: list[str]) -> list[str]:
    """Top-level paths no element's related code covers and `.specignore` doesn't leave out (CHECK-38)."""
    found = patterns(spec.repo_root())
    if found is None:
        return []
    related = [str(p).rstrip("/") for e in spec.elements.values()
               for paths in (e.data.get("related_code") or {}).values() for p in paths or []]
    out = []
    for f in files:
        if f.startswith(ALWAYS_OUT) or f in (FILE,) or ignored(spec.repo_root(), f, found):
            continue
        if any(f == r or f.startswith(r + "/") for r in related):
            continue
        top = f.split("/")[0] + ("/" if "/" in f else "")
        if top not in out:
            out.append(top)
    return out
