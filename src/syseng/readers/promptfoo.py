"""promptfoo's JSON results. A test's identifier is the case's description, from the with-skill arm's runs: the
baseline arm isn't what a verification item claims. A case passes when enough of its runs pass."""

import json
from pathlib import Path

from syseng import readers

ARM = "with-skill"
PASS_RATE = 0.8


def read(path, root):
    try:
        rows = json.loads(Path(path).read_text())["results"]["results"]
    except (ValueError, KeyError, TypeError) as e:
        raise readers.ReaderError(f"{path} isn't promptfoo's JSON output") from e
    runs: dict[str, list[bool]] = {}
    for row in rows:
        labelled = (row.get("provider") or {}).get("label")
        if labelled in (None, ARM):
            runs.setdefault(row["testCase"]["description"], []).append(bool(row.get("success")))
    return {case: readers.PASS if sum(ok) / len(ok) >= PASS_RATE else readers.FAIL for case, ok in runs.items()}
