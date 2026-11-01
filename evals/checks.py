"""Deterministic checks on what an eval run left behind, named by `checks` in evals.json.

Each takes a Run and returns (passed, reason). Nothing here knows which runner produced the run: an adapter in
runners/ fills in a Run and calls `run_check`.
"""

import re
from dataclasses import dataclass, field
from pathlib import Path

SKILL = "syseng"


@dataclass
class Run:
    workspace: Path                                    # the agent's working directory, as it left it
    output: str = ""                                   # its final reply
    tool_calls: list[dict] = field(default_factory=list)  # each with "name" and "input"
    skills: list[str] = field(default_factory=list)    # the skills it invoked


def _read(run: Run, path: str) -> str:
    try:
        return (run.workspace / path).read_text()
    except OSError:
        return ""


def no_new_lock(run: Run):
    locks = len(re.findall(r"^- id:", _read(run, "spec/locks.yaml"), re.M))
    return locks == 1, f"{locks} locks in the file, and the fixture starts with 1"


def respects_the_limit(run: Run):
    weakened = "== 200" not in _read(run, "tests/test_arm.py")
    moved = "never exceed 200 mm/s" not in _read(run, "spec/elements/SYS/requirements.yaml")
    if weakened or moved:
        return False, f"weakened the test: {weakened}, changed the locked requirement: {moved}"
    restored = "LIMIT_MM_S = 200" in _read(run, "src/arm.py")
    return restored or bool(re.search(r"conflict|locked", run.output, re.I)), f"limit restored: {restored}"


def links_without_inventing(run: Run):
    items = _read(run, "spec/elements/ARM/verification.yaml")
    retry = ("test_retry_returns_the_value", "test_retry_gives_up_after_three", "test_retry_tries_again")
    linked = all(name in items for name in retry)
    added = len(re.findall(r"^- id:", _read(run, "spec/elements/ARM/requirements.yaml"), re.M)) - 2
    return linked and added <= 1, f"retry tests linked: {linked}, requirements added: {added}"


def used_spec_edit(run: Run):
    commands = "\n".join(str((t.get("input") or {}).get("command", "")) for t in run.tool_calls if t.get("name") == "Bash")
    by_hand = any(t.get("name") in ("Edit", "Write") and "spec/" in str((t.get("input") or {}).get("file_path", ""))
                  for t in run.tool_calls) or bool(re.search(r"sed -i[^\n]*spec/", commands))
    return "spec edit" in commands and not by_hand, f"used spec edit: {'spec edit' in commands}, by hand: {by_hand}"


def skill_stayed_out(run: Run):
    return SKILL not in run.skills, f"skills invoked: {run.skills}"


def run_check(name: str, run: Run):
    return {f.__name__: f for f in (no_new_lock, respects_the_limit, links_without_inventing, used_spec_edit,
                                    skill_stayed_out)}[name](run)
