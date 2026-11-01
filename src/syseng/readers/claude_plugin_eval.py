"""The JSON that `claude plugin eval --json` writes. A test's identifier is its case's name. A case passes when its
with-skill score reaches the run's threshold; a case the run didn't finish grading counts as skipped."""

import json
from pathlib import Path

from syseng import readers


def _graded(case: dict) -> bool:
    runs = (case.get("arms") or {}).get("with") or []
    return bool(runs) and not any(run.get("skippedPaidGraders") for run in runs)


def read(path, root):
    try:
        data = json.loads(Path(path).read_text())
        threshold, cases = data["suite"]["threshold"], data["cases"]
    except (ValueError, KeyError, TypeError) as e:
        raise readers.ReaderError(f"{path} isn't the JSON from `claude plugin eval --json`") from e
    tests = {}
    for case in cases:
        score = (case.get("aggregates") or {}).get("score")
        if score is None or not _graded(case):
            outcome = readers.SKIP
        else:
            outcome = readers.PASS if score >= threshold else readers.FAIL
        readers.merge(tests, case["name"], outcome)
    return tests
