"""Fingerprints of a spec item's meaning (MODEL-24, DR-5).

A fingerprint covers what the engineer approves: the statement and the prose that gives it
meaning. It leaves out links the checker verifies by itself, such as test links and
related code (MODEL-31), so re-pointing a test never un-approves a requirement.
"""

import hashlib

from syseng.model import Element, Item

MEANING_FIELDS = {
    "need": ("text", "context"),
    "system": ("text",),
    "constraint": ("text",),
    "requirement": ("text",),
    "vi": ("description", "method", "technique", "verifies"),
    "decision": ("title", "status", "context", "decision", "alternatives", "consequences"),
    "element": ("title", "purpose", "parent", "depends_on"),
}


def _normalize(value) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        return ", ".join(str(v) for v in value)
    return " ".join(str(value).split())


def canonical(kind: str, data: dict) -> str:
    return "\n".join(f"{f}: {_normalize(data.get(f))}" for f in MEANING_FIELDS[kind])


def of(kind: str, data: dict) -> str:
    return hashlib.sha256(canonical(kind, data).encode()).hexdigest()[:12]


def of_item(item: Item) -> str:
    return of(item.kind, item.data)


def of_element(element: Element) -> str:
    return of("element", element.data)


def summary(kind: str, data: dict) -> str:
    """The short text an approval record keeps, so a reviewer sees what was approved."""
    if kind == "decision":
        return f"{data.get('title', '')}: {_normalize(data.get('decision'))}"
    if kind == "element":
        return f"{data.get('title', '')}: {_normalize(data.get('purpose'))}"
    if kind == "vi":
        return _normalize(data.get("description"))
    return _normalize(data.get("text"))
