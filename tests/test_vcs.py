"""Version control behind one interface (SYS-59)."""

import re
import subprocess
from pathlib import Path

import pytest

from syseng import vcs

SRC = Path(vcs.__file__).parent.parent


def test_git_is_the_default_backend(tmp_path):
    assert type(vcs.backend(tmp_path)).__name__ == "Git" and "git" in vcs.backends()


def test_the_settings_choose_the_backend(tmp_path):
    (tmp_path / "spec").mkdir()
    (tmp_path / "spec" / "toolkit.yaml").write_text("version_control: piper\n")
    with pytest.raises(vcs.VersionControlError, match="no version-control backend 'piper'; the toolkit has: git"):
        vcs.backend(tmp_path)


def test_a_new_backend_is_found_without_changing_anything_else(tmp_path, monkeypatch):
    (tmp_path / "hg_like.py").write_text("BACKEND = 'found'\n")
    monkeypatch.setattr(vcs, "__path__", [*vcs.__path__, str(tmp_path)])
    (tmp_path / "toolkit.yaml").write_text("version_control: hg_like\n")
    assert vcs.backend(tmp_path) == "found"


def test_nothing_outside_the_backend_calls_git():
    for path in SRC.rglob("*.py"):
        if path.parent.name == "vcs":
            continue
        assert not re.search(r"""\[\s*["']git["']|\.gitignore""", path.read_text()), path


def test_the_git_backend_answers_each_operation(tmp_path):
    git = vcs.backend(tmp_path)
    run = lambda *a: subprocess.run(["git", "-c", "user.name=a", "-c", "user.email=a@b.c", *a], cwd=tmp_path, check=True)
    run("init", "-q")
    (tmp_path / "a.txt").write_text("one")
    run("add", "a.txt")
    run("commit", "-q", "-m", "x")
    run("config", "syseng.author", "Ada")
    run("remote", "add", "origin", "git@example.test:acme/rocket.git")
    revision = git.revision(tmp_path)
    assert git.root(tmp_path).resolve() == tmp_path.resolve()
    assert not git.differs(tmp_path, tmp_path / "a.txt")
    (tmp_path / "a.txt").write_text("two")
    assert git.differs(tmp_path, tmp_path / "a.txt")
    assert git.resolve(tmp_path, revision)[0] == revision
    git.extract(tmp_path, revision, "a.txt", tmp_path / "out")
    assert (tmp_path / "out" / "a.txt").read_text() == "one"
    assert git.setting(tmp_path, "syseng.author") == "Ada"
    assert git.address(tmp_path) == "git@example.test:acme/rocket.git"
    assert revision.startswith(git.short(tmp_path, revision))
    run("checkout", "-q", "-b", "side")
    (tmp_path / "b.txt").write_text("x")
    run("add", "b.txt")
    run("commit", "-q", "-m", "y")
    run("branch", "-q", "main-line", revision)
    assert git.resolve(tmp_path, "main-line")[0] == revision
    (tmp_path / "gen").mkdir()
    git.ignore(tmp_path / "gen")
    git.ignore(tmp_path / "gen")
    assert (tmp_path / ".gitignore").read_text() == "gen/\n"
    with pytest.raises(vcs.VersionControlError):
        git.resolve(tmp_path, "nothing-here")
