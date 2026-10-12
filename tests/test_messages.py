"""Findings teach: each names its rule, explains why, suggests a fix (CHECK-2, CHECK-16), once per run (CHECK-17)."""

from pathlib import Path

from syseng import check
from syseng.rules import RULES


def test_error_explains_rule(spec):
    spec.files["elements/CORE/requirements.yaml"][0]["text"] = "The core shall stamp widgets where possible."
    root = spec.write()
    out = check.format_findings(spec.findings(), root)
    assert "error[W003]" in out and "CORE-1" in out
    assert "requirements.yaml:" in out                       # where
    assert "^^^^^" in out                                    # points at the words
    assert "= why:" in out and "INCOSE R8" in out            # why, with its source
    assert "= fix:" in out                                   # how to fix
    assert "= rule: docs/rules.md#w003" in out               # link to the explanation


def test_rule_explained_once_per_run(spec):
    reqs = spec.files["elements/CORE/requirements.yaml"]
    reqs[0]["text"] = "The core shall stamp widgets where possible."
    reqs.append({"id": "CORE-2", "text": "The core shall polish widgets as needed.", "origin": "agent",
                 "traces_to": "SYS-1", "why": "shiny."})
    root = spec.write()
    out = check.format_findings(spec.findings(), root)
    assert out.count("error[W003]") == 2
    assert out.count("= why:") == 1
    assert "see the first W003 above" in out


def test_summary_counts_errors_and_todos(spec):
    spec.files["elements/CORE/verification.yaml"] = []
    spec.write()
    line = check.summarize(spec.findings())
    assert line.startswith("spec check: 0 errors")
    assert "requirements without verification items" in line


def test_every_rule_is_explained_in_the_rules_page():
    page = (Path(__file__).resolve().parents[1] / "docs" / "rules.md").read_text()
    missing = [code for code in RULES if f'<a id="{code.lower()}"></a>' not in page]
    assert missing == []
