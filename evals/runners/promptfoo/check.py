"""Calls evals/checks.py from a promptfoo assertion. Each function name is a check's name."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import checks  # noqa: E402


def run_from(output, context) -> checks.Run:
    response = context.get("providerResponse") or {}
    meta = response.get("metadata") or {}
    return checks.Run(Path(meta.get("workingDir") or "."), str(output), meta.get("toolCalls") or [],
                      [s.get("name") for s in meta.get("skillCalls") or []])


def _result(name, output, context):
    passed, reason = checks.run_check(name, run_from(output, context))
    return {"pass": passed, "score": 1 if passed else 0, "reason": reason}


def no_new_lock(output, context):
    return _result("no_new_lock", output, context)


def respects_the_limit(output, context):
    return _result("respects_the_limit", output, context)


def links_without_inventing(output, context):
    return _result("links_without_inventing", output, context)


def used_spec_edit(output, context):
    return _result("used_spec_edit", output, context)


def skill_stayed_out(output, context):
    return _result("skill_stayed_out", output, context)
