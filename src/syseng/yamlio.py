"""Reads and writes spec YAML in a stable, diff-friendly style.

Strings that YAML would otherwise quote or escape (quotes, colons, newlines) are written
as literal blocks, so a reviewer reading a raw diff sees the prose exactly as stored.
"""

from pathlib import Path

import yaml


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
    path.write_text(dumps(data))


def read(path: Path):
    return yaml.safe_load(path.read_text())


def loads(text: str):
    return yaml.safe_load(text)
