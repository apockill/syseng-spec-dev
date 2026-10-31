"""The rounds of review a line of work has been through, on any new page (SYS-60)."""

import subprocess

import pytest
import yaml

from syseng import changes, feedback, model, page, pagedata, review

ADA = "Ada <ada@example.com>"


def _git(repo, *args):
    subprocess.run(["git", "-c", "user.name=a", "-c", "user.email=a@b.c", *args], cwd=repo, check=True,
                   capture_output=True)


def _head(repo):
    return subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True).stdout.strip()


@pytest.fixture
def repo(tmp_path):
    (tmp_path / "spec" / "elements" / "SYS").mkdir(parents=True)
    (tmp_path / "spec" / "toolkit.yaml").write_text(yaml.safe_dump({"spec_version": 2, "element_order": ["SYS"]}))
    (tmp_path / "spec" / "elements" / "SYS" / "element.yaml").write_text("id: SYS\ntitle: S\npurpose: P\n")
    (tmp_path / "spec" / "elements" / "SYS" / "needs.yaml").write_text(
        "- id: NEED-1\n  text: The engineer needs it.\n  context: c\n")
    _git(tmp_path, "init", "-q", "-b", "main")
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-qm", "base")
    _git(tmp_path, "switch", "-qc", "work")
    return tmp_path


def _review(repo, name, lock=False, comment=None):
    spec = model.load(repo / "spec")
    item = {"id": "NEED-1", "fingerprint": review.current_fingerprint(spec, "NEED-1")}
    if lock:
        item["lock"] = True
    if comment:
        item["comment"] = comment
    block = yaml.safe_dump({"review": name, "by": ADA, "repository": repo.name, "revision": _head(repo), "dirty": False,
                            "generated": "2026-01-01T00:00-07:00", "items": [item], "decisions": []})
    return feedback.apply(spec, feedback.parse(block))


def _log(repo, moment, request="Add a thing"):
    spec = model.load(repo / "spec")
    change = changes.current(spec) or changes.start(spec, request, None, None, "work")
    change.data["entries"].append({"op": "modify", "id": "NEED-1", "at": moment, "reason": "r"})
    change.save()


def _history(repo):
    return pagedata.build(model.load(repo / "spec"), ADA)["history"]


def _times(repo, *moments):
    path = repo / "spec" / "reviews.yaml"
    rows = yaml.safe_load(path.read_text())
    for row, moment in zip(rows, moments):
        row["at"] = moment
    path.write_text(yaml.safe_dump(rows))


def test_a_review_records_what_the_person_did(repo):
    _review(repo, "r1", lock=True)
    assert yaml.safe_load((repo / "spec" / "reviews.yaml").read_text())[0]["did"] == {"locked": ["NEED-1"]}


def test_rounds_come_in_order_with_what_each_did_and_said(repo):
    _review(repo, "r1", lock=True)
    _review(repo, "r2", comment="Why this?")
    _times(repo, "2026-01-02T10:00-07:00", "2026-01-01T10:00-07:00")
    rounds = _history(repo)["rounds"]
    assert [r["review"] for r in rounds] == ["r2", "r1"] and [r["n"] for r in rounds] == [1, 2]
    assert rounds[1]["did"] == {"locked": ["NEED-1"]}
    assert rounds[0]["comments"][0]["comment"] == "Why this?" and not rounds[0]["comments"][0]["response"]


def test_work_shows_between_the_rounds_it_happened_in(repo):
    _review(repo, "r1")
    _review(repo, "r2")
    _times(repo, "2026-01-01T10:00-07:00", "2026-01-03T10:00-07:00")
    _log(repo, "2026-01-01T09:00-07:00")
    _log(repo, "2026-01-02T10:00-07:00")
    _log(repo, "2026-01-02T11:00-07:00")
    _log(repo, "2026-01-04T10:00-07:00")
    history = _history(repo)
    assert history["before"][0]["changed"] == 1
    assert history["rounds"][0]["then"][0]["changed"] == 2 and history["rounds"][0]["then"][0]["ids"] == ["NEED-1"]
    assert history["rounds"][1]["then"][0]["changed"] == 1


def test_offsets_are_respected_when_ordering(repo):
    _review(repo, "r1")
    _times(repo, "2026-01-01T10:00+00:00")
    _log(repo, "2026-01-01T09:00-07:00")  # 16:00 UTC, after the review
    assert _history(repo)["rounds"][0]["then"][0]["changed"] == 1


def test_only_reviews_since_the_base_are_this_lines_rounds(repo):
    _review(repo, "r1")
    _git(repo, "add", ".")
    _git(repo, "commit", "-qm", "reviewed")
    _git(repo, "switch", "-qc", "next")
    _review(repo, "r2")
    data = pagedata.build(model.load(repo / "spec"), ADA, ["work"])["history"]
    assert [r["review"] for r in data["rounds"]] == ["r2"]


def test_rounds_survive_a_squash_that_removes_their_commits(repo):
    _review(repo, "r1")
    path = repo / "spec" / "reviews.yaml"
    rows = yaml.safe_load(path.read_text())
    rows[0]["revision"] = "0" * 40
    path.write_text(yaml.safe_dump(rows))
    assert [r["review"] for r in _history(repo)["rounds"]] == ["r1"]


def test_an_older_review_without_details_is_said_to_be_so(repo):
    _review(repo, "r1")
    path = repo / "spec" / "reviews.yaml"
    rows = yaml.safe_load(path.read_text())
    del rows[0]["did"]
    path.write_text(yaml.safe_dump(rows))
    assert _history(repo)["rounds"][0]["did"] is None
    assert "wasn't recorded then" in (page.WEB / "review.js").read_text()


def test_agents_can_read_the_history(repo):
    _review(repo, "r1", lock=True)
    data = pagedata.build(model.load(repo / "spec"), ADA)
    text = pagedata.section_text(data, "history")
    assert "round 1:" in text and "locked: NEED-1" in text


def test_the_page_has_the_tab_and_nothing_recommended_says_what_happened():
    script = (page.WEB / "review.js").read_text()
    assert 'history: "Review history"' in script and "See the review history" in script
