"""One JSON object per line: {"id": "...", "outcome": "pass"}, with outcome pass, fail or skip."""

import json
from pathlib import Path

from syseng import readers


def read(path, root):
    tests = {}
    for n, line in enumerate(Path(path).read_text().splitlines(), 1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
            name, outcome = row["id"], row["outcome"]
        except (ValueError, KeyError, TypeError) as e:
            raise readers.ReaderError(f"{path}, line {n}: expected an id and an outcome") from e
        if outcome not in (readers.PASS, readers.FAIL, readers.SKIP):
            raise readers.ReaderError(f"{path}, line {n}: outcome {outcome!r} isn't pass, fail or skip")
        readers.merge(tests, str(name), outcome)
    return tests
