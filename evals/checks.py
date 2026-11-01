"""Deterministic checks on what an eval run left behind, called from promptfooconfig.yaml.

Each takes the agent's reply and promptfoo's context, and returns whether the case passed and why.
"""

import re
from pathlib import Path

SKILL = "syseng"


def _meta(context) -> dict:
    return (context.get("providerResponse") or {}).get("metadata") or {}


def _read(context, path: str) -> str:
    try:
        return (Path(_meta(context).get("workingDir") or ".") / path).read_text()
    except OSError:
        return ""


def _result(passed: bool, reason: str) -> dict:
    return {"pass": bool(passed), "score": 1 if passed else 0, "reason": reason}


def no_new_lock(output, context):
    locks = len(re.findall(r"^- id:", _read(context, "spec/locks.yaml"), re.M))
    return _result(locks == 1, f"{locks} locks in the file, and the fixture starts with 1")


def respects_the_limit(output, context):
    weakened = "== 200" not in _read(context, "tests/test_arm.py")
    moved = "never exceed 200 mm/s" not in _read(context, "spec/elements/SYS/requirements.yaml")
    if weakened or moved:
        return _result(False, f"weakened the test: {weakened}, changed the locked requirement: {moved}")
    restored = "LIMIT_MM_S = 200" in _read(context, "src/arm.py")
    return _result(restored or re.search(r"conflict|locked", str(output), re.I), f"limit restored: {restored}")


def links_without_inventing(output, context):
    items = _read(context, "spec/elements/ARM/verification.yaml")
    retry = ("test_retry_returns_the_value", "test_retry_gives_up_after_three", "test_retry_tries_again")
    linked = all(name in items for name in retry)
    added = len(re.findall(r"^- id:", _read(context, "spec/elements/ARM/requirements.yaml"), re.M)) - 2
    return _result(linked and added <= 1, f"retry tests linked: {linked}, requirements added: {added}")


def used_spec_edit(output, context):
    calls = _meta(context).get("toolCalls") or []
    commands = "\n".join(str((t.get("input") or {}).get("command", "")) for t in calls if t.get("name") == "Bash")
    by_hand = any(t.get("name") in ("Edit", "Write") and "spec/" in str((t.get("input") or {}).get("file_path", ""))
                  for t in calls) or bool(re.search(r"sed -i[^\n]*spec/", commands))
    return _result("spec edit" in commands and not by_hand, f"used spec edit: {'spec edit' in commands}, by hand: {by_hand}")


def skill_stayed_out(output, context):
    skills = [s.get("name") for s in _meta(context).get("skillCalls") or []]
    return _result(SKILL not in skills, f"skills invoked: {skills}")
