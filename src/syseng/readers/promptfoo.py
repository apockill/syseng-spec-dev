"""promptfoo's JSON results. A test's identifier is the case's description, from the with-skill arm's runs: the
baseline arm isn't what a verification item claims. A case passes when enough of its runs pass; a run that errored
was never graded, so it doesn't count, and a case with no graded runs counts as skipped."""

import json
from pathlib import Path

from syseng import readers

ARM = "with-skill"
PASS_RATE = 0.8
ERRORED = 2  # promptfoo's failureReason for a run that didn't finish, as opposed to one that failed its assertions


def read(path, root):
    try:
        rows = json.loads(Path(path).read_text())["results"]["results"]
    except (ValueError, KeyError, TypeError) as e:
        raise readers.ReaderError(f"{path} isn't promptfoo's JSON output") from e
    runs: dict[str, list[bool]] = {}
    for row in rows:
        if (row.get("provider") or {}).get("label") not in (None, ARM):
            continue
        graded = runs.setdefault(row["testCase"]["description"], [])
        if row.get("failureReason") != ERRORED:
            graded.append(bool(row.get("success")))
    return {case: readers.SKIP if not ok else readers.PASS if sum(ok) / len(ok) >= PASS_RATE else readers.FAIL
            for case, ok in runs.items()}
