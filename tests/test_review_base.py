"""What a review page compares against, and that it says so (REVIEW-40 to REVIEW-43)."""

import subprocess

import pytest
import yaml

from syseng import model, page, pagedata

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


def test_the_persons_last_review_stays_a_choice(repo):
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
    assert 'id="compared"' in html.split("</header>")[0]
    assert '"compared":{"label":"main"' in html
    script = (page.WEB / "review.js").read_text()
    assert "Comparing ${cmp.newer} against ${cmp.label} at ${cmp.short}" in script


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
