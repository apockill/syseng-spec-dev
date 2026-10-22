"""Comparing versions of the spec (SYS-48, DIFF-1 to DIFF-5, CLI-26; DR-59)."""

import subprocess

import pytest

from syseng import changes, cli, diff, edit, model, yamlio


def _git(repo, *args):
    return subprocess.run(["git", "-c", "user.name=T", "-c", "user.email=t@example.com", *args], cwd=repo,
                          check=True, capture_output=True, text=True).stdout.strip()


@pytest.fixture
def repo(spec):
    """A repository whose first commit holds the base spec, with CORE-1 locked."""
    root = spec.write()
    assert cli.main(["--spec", str(root), "lock", "SYS-1", "--via", "chat"]) == 0
    spec.files["approvals.yaml"] = yamlio.read(root / "approvals.yaml")
    top = root.parent
    _git(top, "init", "-q", "-b", "main")
    _git(top, "add", "-A")
    _git(top, "commit", "-qm", "base")
    return root


def _edit(root, *ops):
    batch = {"edits": list(ops)}
    result = edit.run(root, batch)
    if result.needs_acks:
        result = edit.run(root, {**batch, "acks": {k: "fine" for k in result.needs_acks}})
    assert result.applied, result.errors


def _start(root):
    changes.start(model.load(root), "widgets", None, None, None)


def test_each_differing_item_gets_its_classes_reasons_and_levels(repo):
    _start(repo)
    _edit(repo,
          {"modify": "SYS-1", "set": {"text": "The system shall make blue widgets."}, "reason": "blue sells"},
          {"modify": "CORE-1", "set": {"text": "The core shall stamp every widget."}, "rewording": True,
           "reason": "plainer"},
          {"modify": "NEED-1", "intent": {"basis": "stated", "context": "Planning.", "said": "Wants widgets."},
           "reason": "their words"},
          {"add": "requirement", "element": "CORE", "id": "CORE-2", "text": "The core shall count each widget.",
           "traces_to": "SYS-1", "basis": "added", "why": "inventory.", "reason": "an extra"})
    d = diff.between(model.load(repo), "HEAD")
    by = {x.id: x for x in d.items}
    assert by["SYS-1"].classes == ["meaning"] and by["SYS-1"].reasons == ["blue sells"]
    assert by["SYS-1"].level_before == "explicit" and "alters what a person locked" in by["SYS-1"].flags
    assert by["CORE-1"].classes == ["reworded"]
    assert by["NEED-1"].classes == ["intent"]
    assert by["CORE-2"].classes == ["added"] and by["CORE-2"].level_after == "added"
    assert by["SYS-1"].before["text"] == "The system shall make widgets."


def test_a_move_and_a_change_are_both_reported(repo):
    _start(repo)
    _edit(repo, {"add": "requirement", "element": "CORE", "id": "CORE-2", "text": "The core shall count each widget.",
                 "traces_to": "SYS-1", "basis": "derived", "why": "inventory.", "reason": "needed"})
    _git(repo.parent, "add", "-A")
    _git(repo.parent, "commit", "-qm", "count")
    _edit(repo, {"modify": "CORE-1", "set": {"traces_to": "CORE-2", "text": "The core shall stamp counted widgets."},
                 "reason": "stamp after counting"})
    by = {x.id: x for x in diff.between(model.load(repo), "HEAD").items}
    assert by["CORE-1"].classes == ["moved", "meaning"]


def test_a_branch_is_compared_at_its_merge_base(repo):
    top = repo.parent
    _git(top, "checkout", "-qb", "feature")
    _start(repo)
    _edit(repo, {"modify": "CORE-1", "set": {"text": "The core shall stamp each widget twice."}, "reason": "twice"})
    _git(top, "add", "-A")
    _git(top, "commit", "-qm", "feature work")
    _git(top, "checkout", "-q", "main")
    reqs = yamlio.read(repo / "elements/SYS/needs.yaml")
    reqs[0]["text"] = "The engineer needs many widgets."
    yamlio.write(repo / "elements/SYS/needs.yaml", reqs)
    _git(top, "commit", "-qam", "newer work on main")
    _git(top, "checkout", "-q", "feature")
    d = diff.between(model.load(repo), "main")
    assert {x.id for x in d.items} >= {"CORE-1"} and "NEED-1" not in {x.id for x in d.items}
    assert "merge base of main" in d.older.note


def test_comparing_leaves_the_working_tree_alone(repo):
    _start(repo)
    _edit(repo, {"modify": "CORE-1", "set": {"text": "The core shall stamp each widget twice."}, "reason": "twice"})
    before = _git(repo.parent, "status", "--porcelain")
    diff.between(model.load(repo), "HEAD")
    assert _git(repo.parent, "status", "--porcelain") == before


def test_a_verification_item_changed_on_its_own_is_flagged(repo):
    _start(repo)
    _edit(repo, {"modify": "CORE-V1", "set": {"description": "A made widget usually carries a stamp."},
                 "reason": "flaky"})
    by = {x.id: x for x in diff.between(model.load(repo), "HEAD").items}
    assert "verification changed while what it verifies didn't" in by["CORE-V1"].flags


def test_an_unknown_name_is_an_error(repo):
    with pytest.raises(diff.DiffError, match="names no branch"):
        diff.between(model.load(repo), "nope")


def test_the_cli_prints_text_and_yaml(repo, capsys):
    _start(repo)
    _edit(repo, {"modify": "CORE-1", "set": {"text": "The core shall stamp each widget twice."}, "reason": "twice"})
    assert cli.main(["--spec", str(repo), "diff"]) == 0
    out = capsys.readouterr().out
    assert "spec diff: HEAD" in out and "CORE-1 [changed in meaning; derived]" in out and "why: twice" in out
    assert cli.main(["--spec", str(repo), "diff", "--format", "yaml"]) == 0
    data = yamlio.loads(capsys.readouterr().out)
    assert data["counts"] == {"meaning": 1} and data["items"][0]["id"] == "CORE-1"


def test_since_review_compares_against_the_revision_the_page_was_made_from(repo):
    rev = _git(repo.parent, "rev-parse", "HEAD")
    yamlio.write(repo / "reviews.yaml", [{"by": "Tess Tester <tess@example.com>", "at": "2026-10-21T10:00-07:00",
                                          "revision": rev, "dirty": False}])
    _start(repo)
    _edit(repo, {"modify": "CORE-1", "set": {"text": "The core shall stamp each widget twice."}, "reason": "twice"})
    d = diff.since_review(model.load(repo), "Tess Tester <tess@example.com>")
    assert d.older.label == "your last review" and [x.id for x in d.items] == ["CORE-1"]
    with pytest.raises(diff.DiffError, match="hasn't sent back a review"):
        diff.since_review(model.load(repo), "Ada <ada@example.com>")
