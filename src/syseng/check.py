"""The checker: finds everything still unfinished in the spec, in one run (CHECK-1).

Findings are errors (the spec is wrong) or to-dos (work not done yet, such as a
requirement with no verification item, CHECK-10). Only errors fail the check, except in
merge mode, where unapproved items become errors too (CHECK-15).
"""

from dataclasses import dataclass
from pathlib import Path

from syseng import fingerprint, render
from syseng.model import Spec
from syseng.rules import METHODS, RULES, TECHNIQUES, check_wording


@dataclass
class Finding:
    code: str
    message: str
    item: str | None = None
    file: Path | None = None
    line: int | None = None
    excerpt: str | None = None
    span: tuple[int, int] | None = None

    @property
    def severity(self) -> str:
        return RULES[self.code].severity


def _f(code, message, item=None, where=None, excerpt=None, span=None) -> Finding:
    file, line = (where.file, where.line) if where is not None else (None, None)
    return Finding(code, message, item, file, line, excerpt, span)


def check(spec: Spec, merge: bool = False) -> list[Finding]:
    out: list[Finding] = []
    out += _structure(spec)
    out += _traces(spec)
    out += _attributes(spec)
    out += _wording(spec)
    out += _verification(spec)
    out += _approvals(spec, merge)
    out += _rendered(spec)
    return out


# ---------------------------------------------------------------- structure
def _structure(spec: Spec) -> list[Finding]:
    out = [Finding("S001", msg, file=path) for path, msg in spec.load_errors]
    for path in spec.nested_element_files:
        out.append(Finding("S004", f"{path.parent.name} sits inside another element's directory", file=path))
    for first, dup in spec.duplicates:
        out.append(_f("S002", f"{dup.id} is also defined in {first.file.parent.name}/{first.file.name}", dup.id, dup))
    retired = spec.retired_ids()
    roots = [e for e in spec.elements.values() if not e.parent]
    root_id = roots[0].id if len(roots) == 1 else None
    for item in spec.items.values():
        if item.id in retired:
            out.append(_f("S003", f"{item.id} was retired (see retired.yaml)", item.id, item))
        if item.kind == "decision":
            expected = (item.data.get("elements") or [None])[0]
        elif item.kind in ("need", "system", "constraint"):
            expected = root_id
        else:
            expected = item.id.split("-")[0]
        if expected and item.element != expected:
            out.append(_f("S008", f"{item.id} belongs in {expected} but is filed under {item.element}",
                          item.id, item))

    if len(roots) != 1:
        out.append(Finding("S005", f"expected exactly one root element, found {len(roots)}: "
                                   f"{', '.join(e.id for e in roots) or 'none'}"))
    for e in spec.elements.values():
        if e.parent and e.parent not in spec.elements:
            out.append(Finding("S005", f"{e.id}'s parent {e.parent} doesn't exist", file=e.file, line=1))
        seen, cur = set(), e
        while cur and cur.parent and cur.parent in spec.elements:
            if cur.id in seen:
                out.append(Finding("S005", f"{e.id}'s parents loop back on themselves", file=e.file, line=1))
                break
            seen.add(cur.id)
            cur = spec.elements[cur.parent]
        for dep in e.depends_on:
            if dep not in spec.elements:
                out.append(Finding("S006", f"{e.id} depends on unknown element {dep}", file=e.file, line=1))
    cycle = _dependency_cycle(spec)
    if cycle:
        out.append(Finding("S006", "dependency cycle: " + " -> ".join(cycle)))
    return out


def _dependency_cycle(spec: Spec) -> list[str] | None:
    state: dict[str, int] = {}
    stack: list[str] = []

    def visit(n: str) -> list[str] | None:
        state[n] = 1
        stack.append(n)
        for d in spec.elements[n].depends_on:
            if d not in spec.elements:
                continue
            if state.get(d) == 1:
                return stack[stack.index(d):] + [d]
            if d not in state:
                found = visit(d)
                if found:
                    return found
        stack.pop()
        state[n] = 2
        return None

    for n in spec.elements:
        if n not in state:
            found = visit(n)
            if found:
                return found
    return None


# ---------------------------------------------------------------- traces
def _traces(spec: Spec) -> list[Finding]:
    out = []
    needs = {i.id for i in spec.of_kind("need")}
    reqs = {i.id for i in spec.requirements()}
    served: set[str] = set()
    for item in spec.of_kind("system", "constraint"):
        serves = item.data.get("serves") or []
        served.update(serves)
        for n in serves:
            if n not in needs:
                out.append(_f("T001", f"{item.id} serves unknown need {n}", item.id, item))
        if item.kind == "system" and not serves and not item.data.get("derived"):
            out.append(_f("T001", f"system requirement {item.id} serves no need", item.id, item))
    for item in spec.of_kind("requirement"):
        parent = item.data.get("traces_to")
        if item.data.get("derived"):
            if not item.data.get("why"):
                out.append(_f("T001", f"{item.id} is derived but doesn't say why", item.id, item))
            continue
        if not parent:
            out.append(_f("T001", f"{item.id} traces to nothing", item.id, item))
        elif parent not in reqs:
            out.append(_f("T001", f"{item.id} traces to {parent}, which isn't a requirement", item.id, item))
    for n in sorted(needs - served, key=_id_key):
        out.append(_f("T002", f"no requirement serves {n}", n, spec.items[n]))
    for item in spec.of_kind("decision"):
        for ref in _ids_in(str(item.data.get("requirements", ""))):
            if ref not in spec.items:
                out.append(_f("T003", f"{item.id} lists {ref}, which doesn't exist", item.id, item))
        for el in item.data.get("elements") or []:
            if el not in spec.elements:
                out.append(_f("T003", f"{item.id} names unknown system element {el}", item.id, item))
    verified = {r for vi in spec.of_kind("vi") for r in (vi.data.get("verifies") or [])}
    for item in spec.requirements():
        if item.id not in verified and not item.data.get("verification_deferred"):
            out.append(_f("T004", f"{item.id} has no verification item yet", item.id, item))
    return out


def _ids_in(text: str) -> list[str]:
    import re
    return re.findall(r"\b(?:[A-Z]+-V?\d+|DR-\d+)\b", text)


def _id_key(s: str):
    head, _, num = s.rpartition("-")
    return (head, int(num.lstrip("V")) if num.lstrip("V").isdigit() else 0)


# ---------------------------------------------------------------- attributes
def _attributes(spec: Spec) -> list[Finding]:
    out = []
    for item in spec.of_kind("need", "system", "constraint", "requirement", "vi"):
        origin = item.data.get("origin")
        if origin not in ("engineer", "agent"):
            out.append(_f("A002", f"{item.id} has origin {origin!r}", item.id, item))
        if not item.data.get("text") and item.kind != "vi":
            out.append(_f("S007", f"{item.id} has no `text`", item.id, item))
    for item in spec.requirements():
        if not (item.data.get("why") or item.data.get("source")):
            out.append(_f("A001", f"{item.id} has neither `why` nor `source`", item.id, item))
    for item in spec.of_kind("decision"):
        if item.data.get("decided_by") not in ("engineer", "agent"):
            out.append(_f("S007", f"{item.id} needs `decided_by: engineer` or `agent`", item.id, item))
        for f in ("title", "context", "decision"):
            if not item.data.get(f):
                out.append(_f("S007", f"{item.id} has no `{f}`", item.id, item))
    return out


# ---------------------------------------------------------------- wording
def _wording(spec: Spec) -> list[Finding]:
    out = []
    for item in spec.requirements():
        text = str(item.data.get("text") or "")
        for issue in check_wording(text):
            out.append(Finding(issue.code, issue.message, item.id, item.file, item.line, text, issue.span))
    return out


# ---------------------------------------------------------------- verification items
def _verification(spec: Spec) -> list[Finding]:
    out = []
    for vi in spec.of_kind("vi"):
        method, technique = vi.data.get("method"), vi.data.get("technique")
        if method not in METHODS:
            out.append(_f("V001", f"{vi.id} has method {method!r}; use one of {', '.join(METHODS)}", vi.id, vi))
        if technique not in TECHNIQUES:
            out.append(_f("V001", f"{vi.id} has technique {technique!r}; use one of {', '.join(TECHNIQUES)}",
                          vi.id, vi))
        if not vi.data.get("description"):
            out.append(_f("V001", f"{vi.id} has no `description`", vi.id, vi))
        verifies = vi.data.get("verifies") or []
        if not verifies:
            out.append(_f("V001", f"{vi.id} verifies nothing", vi.id, vi))
        for r in verifies:
            if r not in spec.items or spec.items[r].kind not in ("system", "constraint", "requirement"):
                out.append(_f("T003", f"{vi.id} verifies {r}, which isn't a requirement", vi.id, vi))
    return out


# ---------------------------------------------------------------- approvals
def _approvals(spec: Spec, merge: bool) -> list[Finding]:
    out = []
    for a in spec.approvals:
        aid = a.get("id")
        if aid not in spec.items and aid not in spec.elements:
            out.append(Finding("A005", f"approval for {aid}, which doesn't exist", aid, spec.root / "approvals.yaml"))
    code = "A004" if merge else "A003"
    for status in approval_status(spec):
        if status["state"] != "approved":
            note = "changed since approval" if status["state"] == "changed" else "never approved"
            out.append(Finding(code, f"{status['id']} is unapproved ({note})", status["id"],
                               status["file"], status["line"]))
    return out


def approval_status(spec: Spec) -> list[dict]:
    """One entry per approvable item: approved, changed since approval, or never approved."""
    rows = []
    approvable = [(i.id, i.kind, i.data, i.file, i.line) for i in spec.items.values()]
    approvable += [(e.id, "element", e.data, e.file, 1) for e in spec.elements.values()]
    for iid, kind, data, file, line in approvable:
        current = fingerprint.of(kind, data)
        a = spec.approval_for(iid)
        state = "never" if not a else ("approved" if a.get("fingerprint") == current else "changed")
        rows.append({"id": iid, "kind": kind, "state": state, "file": file, "line": line,
                     "fingerprint": current})
    return rows


# ---------------------------------------------------------------- rendered views
def _rendered(spec: Spec) -> list[Finding]:
    out = []
    for name, text in render.views(spec).items():
        path = spec.root / name
        if not path.exists() or path.read_text() != text:
            out.append(Finding("R001", f"{name} doesn't match the spec", file=path))
    return out


# ---------------------------------------------------------------- formatting
def format_findings(findings: list[Finding], root: Path) -> str:
    """Rust-style findings (CHECK-16). Each rule is explained in full once per run (CHECK-17)."""
    lines: list[str] = []
    explained: set[str] = set()
    for f in [f for f in findings if f.severity == "error"]:
        rule = RULES[f.code]
        where = ""
        if f.file:
            try:
                rel = f.file.relative_to(root.parent)
            except ValueError:
                rel = f.file
            where = f"{rel}:{f.line}" if f.line else str(rel)
        head = f"error[{f.code}]: {rule.title}" + (f" in {f.item}" if f.item else "") + f": {f.message}"
        lines.append(head)
        if where:
            lines.append(f"  --> {where}")
        if f.excerpt:
            lines.append(f"   | {f.excerpt}")
            if f.span:
                lines.append("   | " + " " * f.span[0] + "^" * max(1, f.span[1] - f.span[0]))
        if f.code in explained:
            lines.append(f"   = see the first {f.code} above")
        else:
            explained.add(f.code)
            lines.append(f"   = why: {rule.why}" + (f" ({rule.ref})" if rule.ref else ""))
            lines.append(f"   = fix: {rule.fix}")
            lines.append(f"   = rule: {rule.link}")
        lines.append("")
    return "\n".join(lines)


def summarize(findings: list[Finding]) -> str:
    errors = [f for f in findings if f.severity == "error"]
    todos = [f for f in findings if f.severity == "todo"]
    unverified = sum(1 for f in todos if f.code == "T004")
    unapproved = sum(1 for f in todos if f.code == "A003")
    parts = [f"{len(errors)} error{'s' if len(errors) != 1 else ''}"]
    if todos:
        parts.append(f"{len(todos)} to-dos ({unverified} requirements without verification items, "
                     f"{unapproved} unapproved items; list them with `spec check --todo`)")
    return "spec check: " + ", ".join(parts)
