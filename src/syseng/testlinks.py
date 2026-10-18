"""Checks that a linked test exists, without building or running anything (CHECK-4).

A link is `path`, a file, or `path::name`, a test in that file:
- in a Python file, a pytest node ID such as `test_x` or `TestThing::test_x`; any `[parameters]` are ignored;
- in a C++ file, a GoogleTest name, `Suite.Test`, declared with TEST, TEST_F, TEST_P or TYPED_TEST;
- in any other file, the name only has to appear in it.

Paths resolve against the implementation's root directory. Anything more, such as listing the tests no
verification item links to, or running them, is left for later.
"""

import re
from pathlib import Path

CPP_SUFFIXES = {".cc", ".cpp", ".cxx", ".c++"}
_GTEST = r"\b(?:TEST|TEST_F|TEST_P|TYPED_TEST|TYPED_TEST_P)\s*\(\s*{suite}\s*,\s*{test}\s*\)"


def missing(base: Path, link: str, cache: dict[Path, str] | None = None) -> str | None:
    """Why a linked test can't be found, or None when it exists."""
    cache = {} if cache is None else cache
    path, _, name = link.partition("::")
    file = base / path
    if not file.is_file():
        return f"there's no file {path}"
    if not name:
        return None
    if file not in cache:
        cache[file] = file.read_text(errors="replace")
    text = cache[file]
    if file.suffix == ".py":
        parts = [re.sub(r"\[.*\]$", "", p) for p in name.split("::")]
        for cls in parts[:-1]:
            if not re.search(rf"^\s*class\s+{re.escape(cls)}\b", text, re.M):
                return f"{path} has no class {cls}"
        if not re.search(rf"^\s*(?:async\s+)?def\s+{re.escape(parts[-1])}\s*\(", text, re.M):
            return f"{path} has no test {parts[-1]}"
        return None
    if file.suffix in CPP_SUFFIXES:
        suite, _, test = name.partition(".")
        if not test:
            return f"{name} isn't a GoogleTest name; write it as Suite.Test"
        if not re.search(_GTEST.format(suite=re.escape(suite), test=re.escape(test)), text):
            return f"{path} has no GoogleTest {name}"
        return None
    return None if name in text else f"{path} doesn't mention {name}"
