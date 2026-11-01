"""The skill evals' neutral parts (SYS-61): the cases, the checks, and how little of the toolkit knows the runner."""

import importlib.util
import json
import sys
from pathlib import Path

import pytest

from syseng import readers

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "evals"))
import checks  # noqa: E402


def _load(path):
    spec = importlib.util.spec_from_file_location(path.stem, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _workspace(tmp_path, **files):
    for path, text in files.items():
        file = tmp_path / path.replace("__", "/")
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text(text)
    return tmp_path


SUITE = json.loads((REPO / "evals" / "evals.json").read_text())


def test_cases_follow_the_agent_skills_format_and_name_real_checks():
    assert SUITE["skill_name"] == "syseng"
    for case in SUITE["evals"]:
        assert case["id"] and case["prompt"] and case["expected_output"]
        assert case.get("assertions") or case.get("checks"), case["id"]
        for name in case.get("checks") or []:
            assert callable(getattr(checks, name)), name


def test_a_second_lock_is_caught(tmp_path):
    run = checks.Run(_workspace(tmp_path, **{"spec__locks.yaml": "- id: A\n"}))
    (tmp_path / "spec" / "locks.yaml").write_text("- id: A\n")
    assert checks.no_new_lock(run)[0]
    (tmp_path / "spec" / "locks.yaml").write_text("- id: A\n- id: B\n")
    assert not checks.no_new_lock(run)[0]


def _arm(tmp_path, test="== 200", limit=200):
    (tmp_path / "tests").mkdir(exist_ok=True)
    (tmp_path / "tests" / "test_arm.py").write_text(f"assert x {test}")
    (tmp_path / "src").mkdir(exist_ok=True)
    (tmp_path / "src" / "arm.py").write_text(f"LIMIT_MM_S = {limit}")
    (tmp_path / "spec" / "elements" / "SYS").mkdir(parents=True, exist_ok=True)
    (tmp_path / "spec" / "elements" / "SYS" / "requirements.yaml").write_text("never exceed 200 mm/s")
    return checks.Run(tmp_path)


def test_the_limit_stands_only_if_the_test_and_the_lock_survive(tmp_path):
    assert checks.respects_the_limit(_arm(tmp_path))[0]
    assert not checks.respects_the_limit(_arm(tmp_path, test="== 250"))[0]
    assert not checks.respects_the_limit(_arm(tmp_path, limit=250))[0]
    run = _arm(tmp_path, limit=250)
    run.output = "This conflicts with the locked limit."
    assert checks.respects_the_limit(run)[0]


def test_linking_passes_only_without_invented_requirements(tmp_path):
    base = tmp_path / "spec" / "elements" / "ARM"
    base.mkdir(parents=True)
    links = "test_retry_returns_the_value test_retry_gives_up_after_three test_retry_tries_again"
    (base / "verification.yaml").write_text(links)
    (base / "requirements.yaml").write_text("- id: A\n- id: B\n- id: C\n")
    assert checks.links_without_inventing(checks.Run(tmp_path))[0]
    (base / "requirements.yaml").write_text("- id: A\n- id: B\n- id: C\n- id: D\n")
    assert not checks.links_without_inventing(checks.Run(tmp_path))[0]


def test_hand_edits_to_the_spec_fail_even_beside_spec_edit(tmp_path):
    good = [{"name": "Bash", "input": {"command": "spec edit <<'YAML'"}}]
    bad = good + [{"name": "Edit", "input": {"file_path": "spec/locks.yaml"}}]
    assert checks.used_spec_edit(checks.Run(tmp_path, tool_calls=good))[0]
    assert not checks.used_spec_edit(checks.Run(tmp_path, tool_calls=bad))[0]


def test_the_skill_staying_out_is_read_from_the_run(tmp_path):
    assert checks.skill_stayed_out(checks.Run(tmp_path))[0]
    assert not checks.skill_stayed_out(checks.Run(tmp_path, skills=["syseng"]))[0]


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


def test_the_adapter_turns_cases_into_a_run_with_and_without_the_skill(tmp_path):
    build = _load(REPO / "evals" / "runners" / "promptfoo" / "build.py")
    config = build.build(SUITE, tmp_path, "/bin/claude")
    assert [p["label"] for p in config["providers"]] == ["with-skill", "without-skill"]
    assert config["providers"][0]["config"]["skills"] == ["syseng"] and config["providers"][1]["config"]["skills"] == []
    assert [t["description"] for t in config["tests"]] == [c["id"] for c in SUITE["evals"]]
    kinds = {a["type"] for t in config["tests"] for a in t["assert"]}
    assert kinds == {"llm-rubric", "python"}


def test_the_adapter_offers_every_check():
    adapter = _load(REPO / "evals" / "runners" / "promptfoo" / "check.py")
    for case in SUITE["evals"]:
        for name in case.get("checks") or []:
            assert callable(getattr(adapter, name)), name


def test_only_the_reader_in_the_toolkit_names_the_runner():
    source = REPO / "src" / "syseng"
    named = {p.relative_to(source).as_posix() for p in source.rglob("*.py") if "promptfoo" in p.read_text()}
    assert named == {"readers/promptfoo.py"}
