"""What a review page compares against, and that it says so (REVIEW-40 to REVIEW-43, REVIEW-52, REVIEW-53)."""

import subprocess

import pytest
import yaml

from syseng import changes, cli, model, page, pagedata

ADA = "Ada <ada@example.com>"


def _git(repo, *args):
    subprocess.run(["git", "-c", "user.name=a", "-c", "user.email=a@b.c", *args], cwd=repo, check=True,
                   capture_output=True)


def _edit(repo, text):
    path = repo / "spec" / "elements" / "SYS" / "needs.yaml"
    path.write_text(f"- id: NEED-1\n  text: {text}\n  context: c\n  basis: derived\n  why: w\n")
    _git(repo, "commit", "-qam", text)


@pytest.fixture
def repo(tmp_path):
    (tmp_path / "spec" / "elements" / "SYS").mkdir(parents=True)
    (tmp_path / "spec" / "toolkit.yaml").write_text(yaml.safe_dump({"spec_version": 2, "element_order": ["SYS"]}))
    (tmp_path / "spec" / "elements" / "SYS" / "element.yaml").write_text("id: SYS\ntitle: S\npurpose: P\n")
    (tmp_path / "spec" / "elements" / "SYS" / "needs.yaml").write_text("[]\n")
    _git(tmp_path, "init", "-q", "-b", "main")
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-qm", "base")
    return tmp_path


def _build(repo, against=None):
    return pagedata.build(model.load(repo / "spec"), ADA, against or [])


def test_with_no_base_named_the_page_compares_against_the_trunk(repo):
    _git(repo, "switch", "-qc", "work")
    _edit(repo, "The engineer needs one.")
    data = _build(repo)
    compared = data["meta"]["compared"]
    assert compared["label"] == "main" and "merge base" in compared["note"] and compared["short"]
    assert data["changes"][0]["older"]["label"] == "main"
    assert data["overview"]["since"] == "main" and data["overview"]["against"] == "the spec at main"


def test_a_stacked_change_compares_against_the_base_it_names(repo):
    _git(repo, "switch", "-qc", "below")
    _edit(repo, "The engineer needs one.")
    _git(repo, "switch", "-qc", "above")
    _edit(repo, "The engineer needs two.")
    data = _build(repo, ["below"])
    assert data["meta"]["compared"]["label"] == "below"
    assert [c["older"]["label"] for c in data["changes"]] == ["below"]
    assert [i["id"] for i in data["changes"][0]["items"]] == ["NEED-1"]
    assert "two" in data["changes"][0]["items"][0]["after"]["text"]


def _head(repo):
    return subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True).stdout.strip()


def test_the_persons_last_review_stays_a_choice(repo):
    _git(repo, "switch", "-qc", "work")
    _edit(repo, "The engineer needs one.")
    (repo / "spec" / "reviews.yaml").write_text(yaml.safe_dump([
        {"by": ADA, "at": "2026-01-01T00:00", "review": "r1", "dirty": False, "revision":
         subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True).stdout.strip()}]))
    data = _build(repo)
    assert [c["older"]["label"] for c in data["changes"]] == ["main", "your last review"]


def test_the_page_says_when_it_found_nothing_to_compare_against(tmp_path, repo):
    _git(repo, "branch", "-m", "main", "side")
    data = _build(repo)
    assert data["meta"]["compared"] is None and data["changes"] == []
    assert "against nothing" in (page.WEB / "review.js").read_text()


def test_the_page_states_its_base_at_the_top(repo):
    _git(repo, "switch", "-qc", "work")
    html = page.render(_build(repo))
    header = html.split("</header>")[0]
    # a badge among the header's details, naming the base and its revision; the full statement on hover or click
    assert 'class="cmp" id="compared"' in header.split('class="meta"')[1] and 'id="compared-detail" hidden' in header
    assert '"compared":{"label":"main"' in html
    script = (page.WEB / "review.js").read_text()
    assert "against ${cmp.text}" in script and "cmp.why" in script
    assert "badge.title = full" in script and "detail.hidden = !open" in script and "cmp.short" in script


def test_a_base_named_by_its_commit_reads_as_that_commit(repo, capsys, monkeypatch):
    base = _head(repo)
    _edit(repo, "The engineer needs one.")
    compared = _build(repo, [base[:7]])["meta"]["compared"]
    assert compared["text"] == f"commit {compared['short']}" and not compared["why"]
    monkeypatch.chdir(repo)
    assert cli.main(["review", "--against", base[:7], "--out", str(repo / "page.html")]) == 0
    out = capsys.readouterr().out
    # the newer side names the commit it stands on, so the base can't be mistaken for it
    assert f"compared working tree (HEAD {_head(repo)[:7]}) against commit {base[:7]}" in out


def test_on_the_trunk_the_page_compares_against_the_last_review(repo):
    """A repository that commits straight to its trunk: comparing with the trunk would show nothing."""
    (repo / "spec" / "reviews.yaml").write_text(yaml.safe_dump([
        {"by": ADA, "at": "2026-01-01T00:00", "review": "r1", "dirty": False, "revision": _head(repo)}]))
    _git(repo, "add", ".")
    _git(repo, "commit", "-qm", "review")
    _edit(repo, "The engineer needs one.")
    data = _build(repo)
    compared = data["meta"]["compared"]
    assert compared["label"] == "your last review" and compared["text"].startswith("your last review at ")
    assert "main, the trunk" in compared["why"] and "last review" in compared["why"]
    assert [i["id"] for i in data["changes"][0]["items"]] == ["NEED-1"]
    assert "last review" in pagedata.section_text(data, "changes")


def test_on_the_trunk_without_a_review_it_compares_against_where_the_change_started(repo):
    before = _head(repo)
    spec = model.load(repo / "spec")
    c = changes.start(spec, "Add a need", None, None, "need")
    assert c.data["started_from"] == before
    _git(repo, "add", ".")
    _git(repo, "commit", "-qm", "open the change")
    _edit(repo, "The engineer needs one.")
    data = _build(repo)
    compared = data["meta"]["compared"]
    assert compared["label"] == f"the commit before {c.id} started" and compared["revision"] == before
    assert compared["text"].endswith(compared["short"]) and "haven't sent a review" in compared["why"]
    assert [i["id"] for i in data["changes"][0]["items"]] == ["NEED-1"]


def test_on_the_trunk_with_nothing_to_go_on_the_page_keeps_the_trunk(repo):
    _edit(repo, "The engineer needs one.")
    compared = _build(repo)["meta"]["compared"]
    assert compared["label"] == "main" and not compared["why"]


def test_a_named_base_on_the_trunk_is_kept(repo):
    (repo / "spec" / "reviews.yaml").write_text(yaml.safe_dump([
        {"by": ADA, "at": "2026-01-01T00:00", "review": "r1", "dirty": False, "revision": _head(repo)}]))
    data = _build(repo, ["main"])
    assert [c["older"]["label"] for c in data["changes"]] == ["main", "your last review"]


def test_the_overview_shows_requirements_added_against_tests_linked(repo):
    _git(repo, "switch", "-qc", "work")
    assert _build(repo)["overview"]["linking"] == {"requirements": 0, "tests": 0}
    sysdir = repo / "spec" / "elements" / "SYS"
    (sysdir / "requirements.yaml").write_text(
        "- id: SYS-1\n  kind: system\n  text: The tool shall do one.\n  serves: []\n  basis: derived\n  why: w\n")
    (sysdir / "verification.yaml").write_text(
        "- id: SYS-V1\n  verifies: [SYS-1]\n  method: test\n  technique: unit test\n  description: One.\n"
        "  tests:\n    python: [a, b]\n")
    assert _build(repo)["overview"]["linking"] == {"requirements": 1, "tests": 2}
    assert "test links added" in (page.WEB / "review.js").read_text()


def test_linked_tests_are_shown_against_the_total(repo):
    (repo / "tests").mkdir()
    (repo / "tests" / "test_a.py").write_text("def test_one():\n    pass\n\n\ndef test_two():\n    pass\n")
    (repo / "spec" / "toolkit.yaml").write_text(yaml.safe_dump({
        "spec_version": 2, "element_order": ["SYS"],
        "implementations": [{"name": "python", "root": ".", "primary": True}]}))
    (repo / "spec" / "elements" / "SYS" / "requirements.yaml").write_text(
        "- id: SYS-1\n  kind: system\n  text: The tool shall do one.\n  serves: []\n  basis: derived\n  why: w\n")
    (repo / "spec" / "elements" / "SYS" / "verification.yaml").write_text(
        "- id: SYS-V1\n  verifies: [SYS-1]\n  method: test\n  technique: unit test\n  description: One.\n"
        "  tests:\n    python: ['tests/test_a.py::test_one']\n")
    measure = next(m for m in _build(repo)["overview"]["measures"] if m["key"] == "linked_tests")
    assert (measure["now"], measure["detail"], measure["percent"]) == (50.0, "1 of 2 tests", True)
