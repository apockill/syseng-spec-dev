"""The git backend."""

import io
import subprocess
import tarfile
from pathlib import Path

from syseng.vcs import Backend, VersionControlError


def _git(repo: Path, *args: str) -> str:
    try:
        run = subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired) as e:
        raise VersionControlError(f"can't run git: {e}") from e
    if run.returncode != 0:
        raise VersionControlError(run.stderr.strip() or f"git {' '.join(args)} failed")
    return run.stdout.strip()


def _quiet(repo: Path, *args: str) -> str:
    try:
        return _git(repo, *args)
    except VersionControlError:
        return ""


def _exists(repo: Path, ref: str) -> bool:
    return bool(_quiet(repo, "rev-parse", "--verify", "--quiet", ref))


def _branch(repo: Path, name: str) -> tuple[str | None, str]:
    """The ref a branch name means, and a note when it was only found on a remote. HEAD, tags and commits
    aren't branches, so a name that resolves as one of those first isn't looked for on a remote."""
    for ref in (f"refs/heads/{name}", f"refs/remotes/{name}"):
        if _exists(repo, ref):
            return ref, ""
    if name != "HEAD" and not _exists(repo, f"{name}^{{commit}}") and _exists(repo, f"refs/remotes/origin/{name}"):
        return f"refs/remotes/origin/{name}", f"{name} exists only as origin/{name}; compared with that"
    return None, ""


class Git(Backend):
    def root(self, path):
        return Path(_git(path, "rev-parse", "--show-toplevel"))

    def revision(self, repo):
        return _quiet(repo, "rev-parse", "HEAD")

    def differs(self, repo, path):
        return bool(_quiet(repo, "status", "--porcelain", "--", str(path)))

    def resolve(self, repo, label, newer=None):
        ref, note = _branch(repo, label)
        if ref:
            base = _git(repo, "merge-base", ref, newer or "HEAD")
            found = f"merge base of {label} and {newer or 'HEAD'}, {self.short(repo, base)}"
            return base, "; ".join(n for n in (note, found) if n)
        rev = _quiet(repo, "rev-parse", "--verify", "--quiet", f"{label}^{{commit}}")
        if not rev:
            raise VersionControlError(f"{label!r} names no branch, tag or commit here")
        return rev, self.short(repo, rev)

    def extract(self, repo, revision, path, into):
        try:
            data = subprocess.run(["git", "archive", "--format=tar", revision, path], cwd=repo, capture_output=True,
                                  timeout=60)
        except (OSError, subprocess.TimeoutExpired) as e:
            raise VersionControlError(f"can't read the spec at {revision}: {e}") from e
        if data.returncode != 0:
            raise VersionControlError(f"the spec didn't exist at {revision[:12]}: {data.stderr.decode().strip()}")
        with tarfile.open(fileobj=io.BytesIO(data.stdout)) as tar:
            tar.extractall(into, filter="data")

    def setting(self, repo, key):
        return _quiet(repo, "config", key)

    def ignore(self, path):
        listing = path.parent / ".gitignore"
        entry = path.name + "/" if path.is_dir() else path.name
        have = listing.read_text().splitlines() if listing.exists() else []
        if entry not in have:
            listing.write_text("\n".join([*have, entry]) + "\n")

    def short(self, repo, revision):
        return _quiet(repo, "rev-parse", "--short", revision) or revision


BACKEND = Git()
