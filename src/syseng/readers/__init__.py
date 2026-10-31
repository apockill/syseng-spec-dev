"""Readers of test-result formats (SYS-58).

A reader is a module in this package with one function, `read(path, root)`, returning {test identifier: outcome}.
Adding one needs no other change: `--format` takes the module's name, with dashes for underscores. The reader owns
how identifiers are built, and they must match what verification items link (MODEL-42). `root` is the
implementation's root directory.
"""

import importlib
import pkgutil
from pathlib import Path

PASS, FAIL, SKIP = "pass", "fail", "skip"
_WORST = {FAIL: 2, PASS: 1, SKIP: 0}


class ReaderError(Exception):
    pass


def names() -> list[str]:
    return sorted(m.name.replace("_", "-") for m in pkgutil.iter_modules(__path__))


def merge(tests: dict[str, str], name: str, outcome: str) -> None:
    """Adds one outcome. A test reported twice, as parametrized cases are, keeps its worst outcome."""
    if name not in tests or _WORST[outcome] > _WORST[tests[name]]:
        tests[name] = outcome


def read(fmt: str, path: Path, root: Path) -> dict[str, str]:
    """A report's outcomes. VERIFY-26: an unknown format says what's available and how to ask for another."""
    if fmt not in names():
        raise ReaderError(f"no reader for format {fmt!r}. Formats: {', '.join(names())}. To ask for one, report it "
                          f"with `spec issue`, which doesn't need your own conversion.")
    try:
        return importlib.import_module(f"{__name__}.{fmt.replace('-', '_')}").read(path, root)
    except (OSError, UnicodeDecodeError) as e:
        raise ReaderError(f"can't read {path}: {e}") from e
