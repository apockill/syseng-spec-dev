"""Problem reports sent as issues, with consent (SYS-56)."""

import re
import subprocess
from pathlib import Path

import pytest

from syseng import cli, issue

REPO = Path(__file__).resolve().parent.parent
GOOD = """## The task
Add a requirement to a web app's spec.

## How the agent went about it
Ran `spec edit` with a batch of two items.

## The problem
The batch was refused twice with error T005, and it wasn't clear which item was wrong.

## How the agent got past it
Split the batch in two.
"""


def _report(tmp_path, text=GOOD):
    path = tmp_path / "report.md"
    path.write_text(text)
    return path


def _sent(monkeypatch):
    calls = []
    monkeypatch.setattr(issue, "send", lambda title, text: calls.append((title, text)) or "https://example.test/1")
    return calls


def test_template_prints_the_sections_and_matches_the_github_form(capsys):
    assert cli.main(["issue", "--template"]) == 0
    printed = capsys.readouterr().out
    assert [f"## {name}" for name in issue.SECTIONS] == [l for l in printed.splitlines() if l.startswith("## ")]
    form = (REPO / ".github/ISSUE_TEMPLATE/agent-report.md").read_text()
    assert form.split("---\n", 2)[2] == printed


def test_an_empty_section_is_refused(tmp_path, capsys, monkeypatch):
    assert issue.problems(issue.TEMPLATE) == [f"the section `{n}` is empty" for n in issue.SECTIONS]
    assert issue.problems(GOOD) == []
    calls = _sent(monkeypatch)
    assert cli.main(["issue", str(_report(tmp_path, issue.TEMPLATE)), "--title", "T", "--send", "anything"]) == 1
    assert calls == []


def test_a_section_of_its_own_is_refused(tmp_path, capsys, monkeypatch):
    calls = _sent(monkeypatch)
    path = _report(tmp_path, GOOD + "\n## Proposed fix\nAdd a flag.\n")
    assert cli.main(["issue", str(path), "--title", "Refused batch", "--send", "anything"]) == 1
    assert "proposes no solution" in capsys.readouterr().out
    assert calls == []


def test_only_the_template_s_sections_pass():
    for extra in ("### Proposed fix\nAdd a flag.\n", " ## Proposed fix\nAdd a flag.\n", "## The problem\nAgain.\n"):
        assert issue.problems(GOOD + extra), extra
    assert issue.problems("Add a flag.\n" + GOOD) == ["there is text before the first section"]
    assert issue.problems(GOOD.replace("\n", "\r\n")) == []


def test_leaks_are_found():
    text = "Mail ada@example.com about /home/ada/app, ~/app and Ada Lovelace's fork of Acme/rocket."
    found = issue.leaks(text, "Ada Lovelace", "git@github.com:acme/rocket.git")
    assert found == ["email address ada@example.com", "absolute path on line 1", "the author's name, Ada",
                     "the author's name, Lovelace", "this repository's address, acme/rocket"]
    assert issue.leaks(GOOD + "See spec/toolkit.yaml, src/a/b.py and https://example.test/a/b", "Ada Lovelace", "") == []


@pytest.mark.parametrize("path", ["/data/app/x", "/Volumes/a/b", "C:\\Users\\ada", "file:///srv/x"])
def test_absolute_paths_are_found_under_any_root(path):
    assert issue.leaks(f"see {path}", "", "")


@pytest.mark.parametrize("remote", ["ssh://git@github.com:22/acme/rocket.git", "https://github.com/acme/rocket/"])
def test_the_repository_is_found_from_any_form_of_remote(remote):
    assert issue.leaks("a fork of acme/rocket", "", remote)


def test_a_leak_split_by_a_comment_stops_the_send(tmp_path, capsys, monkeypatch):
    calls = _sent(monkeypatch)
    path = _report(tmp_path, GOOD.replace("a web app's spec", "ada@ex<!-- -->ample.com"))
    assert cli.main(["issue", str(path), "--title", "Refused batch"]) == 1
    assert "email address" in capsys.readouterr().out
    assert calls == []


def _code(path, capsys):
    cli.main(["issue", str(path), "--title", "Refused batch"])
    out = capsys.readouterr().out
    return out, re.search(r"--send (\w+)", out)[1]


def test_a_leak_stops_the_send(tmp_path, capsys, monkeypatch):
    calls = _sent(monkeypatch)
    path = _report(tmp_path, GOOD.replace("a web app's spec", "/var/lib/app"))
    assert cli.main(["issue", str(path), "--title", "Refused batch", "--send", "anything"]) == 1
    assert "nothing was sent" in capsys.readouterr().out
    assert calls == []


def test_without_send_it_shows_the_text_and_sends_nothing(tmp_path, capsys, monkeypatch):
    calls = _sent(monkeypatch)
    out, _ = _code(_report(tmp_path), capsys)
    assert issue.REPOSITORY in out and "Title: [agent report] Refused batch" in out and "error T005" in out
    assert calls == []


def test_send_sends_exactly_what_the_preview_showed(tmp_path, capsys, monkeypatch):
    path = _report(tmp_path)
    shown, send_code = _code(path, capsys)
    runs = []

    def gh(argv, input=None, **kwargs):
        runs.append((argv, input))
        return subprocess.CompletedProcess(argv, 0, "https://example.test/1\n" if argv[0] == "gh" else "", "")
    monkeypatch.setattr(issue.shutil, "which", lambda name: "/bin/gh")
    monkeypatch.setattr(issue.subprocess, "run", gh)
    assert cli.main(["issue", str(path), "--title", "Refused batch", "--send", send_code]) == 0
    argv, text = next(r for r in runs if r[0][:3] == ["gh", "issue", "create"])
    assert f"Title: {argv[argv.index('--title') + 1]}\n\n{text}" in shown
    assert argv[argv.index("--repo") + 1] == issue.REPOSITORY


def test_a_report_edited_after_its_preview_is_not_sent(tmp_path, capsys, monkeypatch):
    calls = _sent(monkeypatch)
    path = _report(tmp_path)
    _, send_code = _code(path, capsys)
    path.write_text(GOOD.replace("twice", "three times"))
    assert cli.main(["issue", str(path), "--title", "Refused batch", "--send", send_code]) == 1
    assert "nothing was sent" in capsys.readouterr().out
    assert calls == []


def test_a_failed_send_prints_the_text_for_the_engineer(tmp_path, capsys, monkeypatch):
    def fail(title, text):
        raise RuntimeError("gh isn't signed in")
    monkeypatch.setattr(issue, "send", fail)
    path = _report(tmp_path)
    _, send_code = _code(path, capsys)
    assert cli.main(["issue", str(path), "--title", "Refused batch", "--send", send_code]) == 1
    out = capsys.readouterr().out
    assert "nothing was sent" in out and "error T005" in out and "Title: [agent report]" in out


def test_a_missing_report_file_is_reported(tmp_path, capsys):
    assert cli.main(["issue", str(tmp_path / "none.md"), "--title", "Refused batch"]) == 1
    assert "can't read" in capsys.readouterr().out
