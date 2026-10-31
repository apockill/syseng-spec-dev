"""Everything the toolkit needs from version control, behind one interface (SYS-59).

A backend is a module in this package with a `BACKEND` object. Adding one needs no other change: it's chosen by
`version_control` in toolkit.yaml, git by default (VCS-4). A revision is an opaque name, a commit or a CL number,
that the toolkit only compares for equality (VCS-2).
"""

import importlib
import pkgutil
from abc import ABC, abstractmethod
from pathlib import Path

import yaml

DEFAULT = "git"


class VersionControlError(Exception):
    pass


class Backend(ABC):
    @abstractmethod
    def root(self, path: Path) -> Path:
        """The top of the repository holding `path`."""

    @abstractmethod
    def revision(self, repo: Path) -> str:
        """The name of the current revision, or "" when there is none."""

    @abstractmethod
    def differs(self, repo: Path, path: Path) -> bool:
        """Whether `path` in the working tree differs from the current revision."""

    @abstractmethod
    def resolve(self, repo: Path, label: str, newer: str | None = None) -> tuple[str, str]:
        """The revision a label names, and a note on how it was found. A line of work, such as a branch, resolves
        to its base with `newer`, the current revision when that's None."""

    @abstractmethod
    def trunk(self, repo: Path) -> str:
        """A label for the line of work everything lands on, or "" when there's no telling."""

    @abstractmethod
    def extract(self, repo: Path, revision: str, path: str, into: Path) -> None:
        """Copies `path`, relative to the repository's top, as it was at a revision into a directory."""

    @abstractmethod
    def setting(self, repo: Path, key: str) -> str:
        """A setting from version control's configuration, or ""."""

    @abstractmethod
    def address(self, repo: Path) -> str:
        """Where the repository is hosted, or ""."""

    @abstractmethod
    def ignore(self, path: Path) -> None:
        """Keeps a generated file or folder out of version control."""

    def short(self, repo: Path, revision: str) -> str:
        """A revision's name as shown to people."""
        return revision


def backends() -> list[str]:
    return sorted(m.name for m in pkgutil.iter_modules(__path__))


def _chosen(path: Path) -> str:
    start = path.resolve()
    for d in [start, *start.parents]:
        for settings in (d / "toolkit.yaml", d / "spec" / "toolkit.yaml"):
            if settings.exists():
                return (yaml.safe_load(settings.read_text()) or {}).get("version_control") or DEFAULT
    return DEFAULT


def backend(path: Path) -> Backend:
    """The backend for the repository at `path`."""
    name = _chosen(path)
    if name not in backends():
        raise VersionControlError(f"no version-control backend {name!r}; the toolkit has: {', '.join(backends())}")
    return importlib.import_module(f"{__name__}.{name}").BACKEND
