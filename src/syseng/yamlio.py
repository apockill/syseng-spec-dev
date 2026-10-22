"""Reads and writes spec YAML in a stable, diff-friendly style.

Strings that YAML would otherwise quote or escape (quotes, colons, newlines) are written
as literal blocks, so a reviewer reading a raw diff sees the prose exactly as stored.
"""

import copy
from pathlib import Path

import yaml

_Loader = getattr(yaml, "CSafeLoader", yaml.SafeLoader)  # libyaml's parser where PyYAML was built with it
_cache: dict[str, tuple[int, int, object]] = {}  # parsed files, by path, kept while size and mtime match


class _Dumper(yaml.SafeDumper):
    pass


_BLOCK_STARTS = tuple("\"'[]{}&*!|>%@`#,?-")


def _needs_block(text: str) -> bool:
    return (
        "\n" in text
        or text.startswith(_BLOCK_STARTS)
        or ": " in text
        or " #" in text
        or text != text.strip()
    )


def _represent_str(dumper: yaml.SafeDumper, text: str) -> yaml.Node:
    if text and _needs_block(text):
        return dumper.represent_scalar("tag:yaml.org,2002:str", text, style="|")
    return dumper.represent_scalar("tag:yaml.org,2002:str", text)


_Dumper.add_representer(str, _represent_str)


def dumps(data) -> str:
    return yaml.dump(data, Dumper=_Dumper, sort_keys=False, allow_unicode=True, width=10_000)


def write(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    _cache.pop(str(path.resolve()), None)
    path.write_text(dumps(data))


def read(path: Path):
    """Parses a file once per version of it: an edit reads every change record several times (CHECK-12)."""
    key, st = str(path.resolve()), path.stat()
    hit = _cache.get(key)
    if hit is None or hit[:2] != (st.st_mtime_ns, st.st_size):
        hit = (st.st_mtime_ns, st.st_size, yaml.load(path.read_text(), Loader=_Loader))
        _cache[key] = hit
    return copy.deepcopy(hit[2])  # callers edit what they read


def loads(text: str):
    return yaml.load(text, Loader=_Loader)
