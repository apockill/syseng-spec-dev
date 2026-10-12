"""Loads a spec directory into memory.

Layout (DR-28):
  spec/toolkit.yaml                      project settings: implementations, element order
  spec/approvals.yaml                    the engineer's approvals, one per spec item
  spec/retired.yaml                      IDs that were removed and may never be reused
  spec/questions.yaml                    open and resolved questions
  spec/elements/<ID>/element.yaml        a system element's definition
  spec/elements/<ID>/needs.yaml          needs (normally only on the system element)
  spec/elements/<ID>/requirements.yaml   system requirements, constraints or element requirements
  spec/elements/<ID>/verification.yaml   verification items
  spec/elements/<ID>/decisions.yaml      decision records whose first-listed element is <ID>

Loading never raises on bad content: problems are collected in `Spec.load_errors` so the
checker can report all of them in one run (CHECK-1).
"""

import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from syseng import yamlio

ITEM_FILES = {
    "needs.yaml": "need",
    "requirements.yaml": "requirement",
    "verification.yaml": "vi",
    "decisions.yaml": "decision",
}


@dataclass
class Item:
    id: str
    kind: str  # need | system | constraint | requirement | vi | decision
    data: dict
    element: str
    file: Path
    line: int


@dataclass
class Element:
    id: str
    data: dict
    dir: Path
    file: Path
    line: int

    @property
    def parent(self) -> str | None:
        return self.data.get("parent")

    @property
    def depends_on(self) -> list[str]:
        return list(self.data.get("depends_on") or [])

    @property
    def title(self) -> str:
        return self.data.get("title", "")


@dataclass
class Spec:
    root: Path
    config: dict = field(default_factory=dict)
    elements: dict[str, Element] = field(default_factory=dict)
    items: dict[str, Item] = field(default_factory=dict)
    duplicates: list[tuple[Item, Item]] = field(default_factory=list)
    approvals: list[dict] = field(default_factory=list)
    retired: list[dict] = field(default_factory=list)
    questions: list[dict] = field(default_factory=list)
    load_errors: list[tuple[Path, str]] = field(default_factory=list)
    nested_element_files: list[Path] = field(default_factory=list)

    def of_kind(self, *kinds: str) -> list[Item]:
        return [i for i in self.items.values() if i.kind in kinds]

    def requirements(self) -> list[Item]:
        return self.of_kind("system", "constraint", "requirement")

    def retired_ids(self) -> set[str]:
        return {i for r in self.retired for i in (r.get("ids") or [])}

    def element_order(self) -> list[str]:
        listed = [e for e in (self.config.get("element_order") or []) if e in self.elements]
        return listed + sorted(e for e in self.elements if e not in listed)

    def approval_for(self, item_id: str) -> dict | None:
        for a in self.approvals:
            if a.get("id") == item_id:
                return a
        return None


def _line_of(text: str, item_id: str) -> int:
    m = re.search(r"^\s*(?:-\s+)?id:\s*['\"]?" + re.escape(item_id) + r"['\"]?\s*$", text, re.M)
    return text[: m.start()].count("\n") + 1 if m else 1


def _read(spec: Spec, path: Path):
    try:
        return yamlio.read(path)
    except (OSError, yaml.YAMLError) as e:
        spec.load_errors.append((path, f"can't read YAML: {e}"))
        return None


def find_spec_root(start: Path) -> Path | None:
    """Finds the spec directory: `start` itself, or `spec/` in `start` or any parent."""
    start = start.resolve()
    if (start / "toolkit.yaml").exists():
        return start
    for d in [start, *start.parents]:
        if (d / "spec" / "toolkit.yaml").exists():
            return d / "spec"
    return None


def load(root: Path) -> Spec:
    spec = Spec(root=root)
    spec.config = _read(spec, root / "toolkit.yaml") or {}
    for name, attr in (("approvals.yaml", "approvals"), ("retired.yaml", "retired"), ("questions.yaml", "questions")):
        path = root / name
        if path.exists():
            data = _read(spec, path)
            if data is not None and not isinstance(data, list):
                spec.load_errors.append((path, "must be a list"))
                data = None
            setattr(spec, attr, data or [])

    elements_dir = root / "elements"
    for path in sorted(elements_dir.glob("**/element.yaml")):
        if path.parent.parent != elements_dir:
            spec.nested_element_files.append(path)
    for edir in sorted(p for p in elements_dir.iterdir() if p.is_dir()) if elements_dir.exists() else []:
        efile = edir / "element.yaml"
        if not efile.exists():
            spec.load_errors.append((edir, "system element directory has no element.yaml"))
            continue
        data = _read(spec, efile)
        if not isinstance(data, dict) or "id" not in data:
            spec.load_errors.append((efile, "element.yaml must be a mapping with an `id`"))
            continue
        element = Element(id=str(data["id"]), data=data, dir=edir, file=efile, line=1)
        if element.id in spec.elements:
            spec.load_errors.append((efile, f"system element {element.id} is defined twice"))
            continue
        spec.elements[element.id] = element
        for fname, kind in ITEM_FILES.items():
            path = edir / fname
            if not path.exists():
                continue
            entries = _read(spec, path)
            if entries is None:
                continue
            if not isinstance(entries, list):
                spec.load_errors.append((path, "must be a list of items"))
                continue
            text = path.read_text()
            for entry in entries:
                if not isinstance(entry, dict) or "id" not in entry:
                    spec.load_errors.append((path, f"every entry needs an `id`; found {entry!r:.60}"))
                    continue
                item_kind = kind
                if kind == "requirement" and entry.get("kind") in ("system", "constraint"):
                    item_kind = entry["kind"]
                item = Item(id=str(entry["id"]), kind=item_kind, data=entry, element=element.id,
                            file=path, line=_line_of(text, str(entry["id"])))
                if item.id in spec.items:
                    spec.duplicates.append((spec.items[item.id], item))
                else:
                    spec.items[item.id] = item
    return spec
