"""This repository's evals of its skill: the cases, the checks, and how little of the toolkit knows the eval tool."""

import importlib.util
import json
from pathlib import Path

import pytest
import yaml

from syseng import readers

REPO = Path(__file__).resolve().parent.parent
SUITE = yaml.safe_load((REPO / "evals" / "promptfooconfig.yaml").read_text())
_spec = importlib.util.spec_from_file_location("eval_checks", REPO / "evals" / "checks.py")
checks = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(checks)


def _context(workspace=".", tool_calls=(), skills=()):
    return {"providerResponse": {"metadata": {"workingDir": str(workspace), "toolCalls": list(tool_calls),
                                              "skillCalls": [{"name": n} for n in skills]}}}


def _passed(result):
    return result["pass"]


def test_every_case_is_named_graded_and_calls_a_real_check():
    for case in SUITE["tests"]:
        assert case["description"] and case["vars"]["request"] and case["assert"], case
        for grader in case["assert"]:
            if grader["type"] == "python":
                assert callable(getattr(checks, grader["value"].rpartition(":")[2])), grader


def test_a_second_lock_is_caught(tmp_path):
    (tmp_path / "spec").mkdir()
    (tmp_path / "spec" / "locks.yaml").write_text("- id: A\n")
    assert _passed(checks.no_new_lock("", _context(tmp_path)))
    (tmp_path / "spec" / "locks.yaml").write_text("- id: A\n- id: B\n")
    assert not _passed(checks.no_new_lock("", _context(tmp_path)))


def _arm(tmp_path, test="== 200", limit=200):
    (tmp_path / "tests").mkdir(exist_ok=True)
    (tmp_path / "tests" / "test_arm.py").write_text(f"assert x {test}")
    (tmp_path / "src").mkdir(exist_ok=True)
    (tmp_path / "src" / "arm.py").write_text(f"LIMIT_MM_S = {limit}")
    (tmp_path / "spec" / "elements" / "SYS").mkdir(parents=True, exist_ok=True)
    (tmp_path / "spec" / "elements" / "SYS" / "requirements.yaml").write_text("never exceed 200 mm/s")
    return _context(tmp_path)


def test_the_limit_stands_only_if_the_test_and_the_lock_survive(tmp_path):
    assert _passed(checks.respects_the_limit("", _arm(tmp_path)))
    assert not _passed(checks.respects_the_limit("", _arm(tmp_path, test="== 250")))
    assert not _passed(checks.respects_the_limit("", _arm(tmp_path, limit=250)))
    assert _passed(checks.respects_the_limit("This conflicts with the locked limit.", _arm(tmp_path, limit=250)))


def test_linking_passes_only_without_invented_requirements(tmp_path):
    base = tmp_path / "spec" / "elements" / "ARM"
    base.mkdir(parents=True)
    links = "test_retry_returns_the_value test_retry_gives_up_after_three test_retry_tries_again"
    (base / "verification.yaml").write_text(links)
    (base / "requirements.yaml").write_text("- id: A\n- id: B\n- id: C\n")
    assert _passed(checks.links_without_inventing("", _context(tmp_path)))
    (base / "requirements.yaml").write_text("- id: A\n- id: B\n- id: C\n- id: D\n")
    assert not _passed(checks.links_without_inventing("", _context(tmp_path)))


def test_hand_edits_to_the_spec_fail_even_beside_spec_edit():
    good = [{"name": "Bash", "input": {"command": "spec edit <<'YAML'"}}]
    bad = good + [{"name": "Edit", "input": {"file_path": "spec/locks.yaml"}}]
    assert _passed(checks.used_spec_edit("", _context(tool_calls=good)))
    assert not _passed(checks.used_spec_edit("", _context(tool_calls=bad)))


def test_the_skill_staying_out_is_read_from_the_run():
    assert _passed(checks.skill_stayed_out("", _context()))
    assert not _passed(checks.skill_stayed_out("", _context(skills=["syseng"])))


def _rows(*rows):
    return {"results": {"results": [{"provider": {"label": arm}, "testCase": {"description": case}, "success": ok}
                                    for case, arm, ok in rows]}}


def test_a_case_passes_on_its_with_skill_pass_rate(tmp_path):
    path = tmp_path / "r.json"
    path.write_text(json.dumps(_rows(
        ("a", "with-skill", True), ("a", "with-skill", True), ("a", "with-skill", True), ("a", "without-skill", False),
        ("b", "with-skill", True), ("b", "with-skill", False), ("b", "without-skill", True))))
    assert readers.read("promptfoo", path, tmp_path) == {"a": "pass", "b": "fail"}


def test_a_file_that_isnt_a_promptfoo_run_is_named(tmp_path):
    path = tmp_path / "r.json"
    path.write_text("[]")
    with pytest.raises(readers.ReaderError, match="promptfoo"):
        readers.read("promptfoo", path, tmp_path)


def test_only_the_reader_in_the_toolkit_names_the_eval_tool():
    source = REPO / "src" / "syseng"
    named = {p.relative_to(source).as_posix() for p in source.rglob("*.py") if "promptfoo" in p.read_text()}
    assert named == {"readers/promptfoo.py"}
