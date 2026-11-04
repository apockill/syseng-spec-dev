"""Reads and writes spec YAML in a stable, diff-friendly style.

Strings that YAML would otherwise quote or escape (quotes, colons, newlines) are written
as literal blocks, so a reviewer reading a raw diff sees the prose exactly as stored.
"""

import copy
import re
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


# ---------------------------------------------------------------- batches agents send (CLI-36, CLI-37, DR-80)
class BatchError(ValueError):
    pass


# Fields that hold prose: YAML ends an unquoted value at ` #`, so "uses the #090d16 background" would be stored as
# "uses the". A comment after any of these on the same line is refused.
PROSE = frozenset({
    "text", "title", "why", "said", "context", "reason", "description", "question", "importance", "detail", "label",
    "words", "request", "decision", "alternatives", "consequences", "comment", "correction", "wording", "purpose",
    "note", "response", "allocation_note", "verification_deferred", "workaround", "proposal", "general"})
_ID = re.compile(r"^[A-Z][A-Z0-9]*-V?\d+$")  # an acknowledgment's note sits under the item's ID
_KEY = re.compile(r"^\s*(?:-\s+)?([^\s:#][^:#]*?)\s*:(?:\s|$)")


def loads_batch(text: str):
    """Parses YAML an agent sent, refusing what YAML would read differently from what the agent meant: a comment
    that cuts a prose value short (CLI-36), and a colon inside a value that ends it early (CLI-37)."""
    lines = text.splitlines()
    try:
        node = yaml.compose(text, Loader=yaml.SafeLoader)
    except yaml.MarkedYAMLError as e:
        raise BatchError(_explain(e, lines)) from None
    cut = []
    _cut_values(node, None, lines, cut)
    if cut:
        raise BatchError("YAML reads ` #` as the start of a comment, so these values would be cut short there:\n"
                         + "\n".join(f"  line {n}: `{key}` would be stored as {value!r}; the rest, {rest!r}, would "
                                     f"be dropped" for n, key, value, rest in cut)
                         + "\nPut each value in quotes (`text: \"… #090d16 …\"`) or use a block (`text: |`), and put "
                           "comments on lines of their own. Nothing was written.")
    return loads(text)


def _cut_values(node, key, lines: list[str], out: list) -> None:
    if isinstance(node, yaml.MappingNode):
        for k, v in node.value:
            _cut_values(v, str(k.value) if isinstance(k, yaml.ScalarNode) else None, lines, out)
    elif isinstance(node, yaml.SequenceNode):
        for v in node.value:
            _cut_values(v, key, lines, out)
    elif isinstance(node, yaml.ScalarNode) and node.style is None and node.value and key is not None:
        line = lines[node.end_mark.line] if node.end_mark.line < len(lines) else ""
        rest = line[node.end_mark.column:]
        if not rest.lstrip().startswith("#"):
            return
        comment = rest.lstrip()
        # a comment after a prose field always cuts it short; after any other value, a `#` glued to the word after
        # it (`#090d16`, `#12`) is part of the value the agent meant, not a comment (DR-80)
        if key in PROSE or _ID.match(key) or not comment[1:2].isspace() and comment[1:2] != "":
            out.append((node.end_mark.line + 1, key, node.value, comment))


def _explain(e: yaml.MarkedYAMLError, lines: list[str]) -> str:
    mark = e.problem_mark or e.context_mark
    where = f"line {mark.line + 1}, column {mark.column + 1}" if mark else "somewhere"
    if mark and "mapping values are not allowed" in str(e.problem or ""):
        line = lines[mark.line] if mark.line < len(lines) else ""
        m = _KEY.match(line)
        key = f"the value of `{m.group(1)}`" if m else "a value"
        return (f"can't read the YAML you sent: at {where}, {key} holds `: `, which YAML reads as the start of another "
                f"key. Put the value in quotes, or write it as a block (`{m.group(1) if m else 'text'}: |` with the "
                f"text on the lines below).\n  line {mark.line + 1}: {line.strip()}")
    return f"can't read the YAML you sent: {e.problem or e} at {where}" + (
        f"\n  line {mark.line + 1}: {lines[mark.line].strip()}" if mark and mark.line < len(lines) else "")
