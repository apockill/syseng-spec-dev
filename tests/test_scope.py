"""What a spec covers, and what it leaves out through .specignore (SYS-62)."""

import subprocess

from syseng import check, init, model, scope


def _repo(spec, ignore=None, related=None):
    root = spec.write()
    repo = root.parent
    for path in ("portal/app.py", "desklab/arm.py", "README.md", "tests/test_desk.py"):
        (repo / path).parent.mkdir(parents=True, exist_ok=True)
        (repo / path).write_text("def test_x():\n    pass\n" if "test_" in path else "x\n")
    if ignore is not None:
        (repo / ".specignore").write_text(ignore)
    if related is not None:
        spec.files["elements/CORE/element.yaml"]["related_code"] = {"python": related}
        spec.write()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    return repo


def test_patterns_match_folders_files_and_globs(tmp_path):
    (tmp_path / ".specignore").write_text("# apps left out\ndesklab/\n*.log\nnotes.md\n")
    assert scope.ignored(tmp_path, "desklab/arm.py") and scope.ignored(tmp_path, "desklab")
    assert scope.ignored(tmp_path, "logs/run.log") and scope.ignored(tmp_path, "notes.md")
    assert not scope.ignored(tmp_path, "portal/app.py") and not scope.ignored(tmp_path, "desklabs/x.py")
    assert scope.patterns(tmp_path / "nowhere") is None


def test_without_a_specignore_nothing_is_listed(spec):
    _repo(spec)
    assert "T006" not in spec.codes(severity="todo")


def test_paths_neither_related_nor_ignored_are_listed(spec):
    _repo(spec, ignore="desklab/\n", related=["portal/"])
    messages = [f.message for f in spec.findings() if f.code == "T006"]
    assert any(m.startswith("README.md ") for m in messages) and any(m.startswith("tests/ ") for m in messages)
    assert not any(m.startswith(("portal/", "desklab/", "spec/")) for m in messages)


def test_ignored_tests_are_not_asked_to_be_linked(spec):
    _repo(spec, ignore="tests/test_desk.py\n")
    messages = [f.message for f in spec.findings() if f.code == "V003"]
    assert not any("test_desk" in m for m in messages)


def test_the_instructions_say_ignored_paths_need_no_spec():
    assert "`.specignore` are outside the spec" in init.INSTRUCTIONS
