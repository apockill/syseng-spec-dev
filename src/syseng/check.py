"""The checker: finds everything still unfinished in the spec, in one run (CHECK-1).

Findings are errors (the spec is wrong) or to-dos (work not done yet, such as a
requirement with no verification item, CHECK-10). Only errors fail the check, in every
mode: whether a branch lands is the engineer's call (CHECK-15, DR-31).
"""

from dataclasses import dataclass
from pathlib import Path

from syseng import levels, records, render, review, testlinks
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
    level: str | None = None  # overrides the rule's severity, for rules a repository's settings make errors

    @property
    def severity(self) -> str:
        return self.level or RULES[self.code].severity


def _f(code, message, item=None, where=None, excerpt=None, span=None) -> Finding:
    file, line = (where.file, where.line) if where is not None else (None, None)
    return Finding(code, message, item, file, line, excerpt, span)


def check(spec: Spec) -> list[Finding]:
    out: list[Finding] = []
    out += _structure(spec)
    out += _traces(spec)
    out += _attributes(spec)
    out += _wording(spec)
    out += _verification(spec)
    out += _test_links(spec)
    out += _approvals(spec)
    out += _conflicts(spec)
    out += _feedback(spec)
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
    out += _flow_down(spec)
    verified = {r for vi in spec.of_kind("vi") for r in (vi.data.get("verifies") or [])}
    refined = {str(i.data.get("traces_to")) for i in spec.of_kind("requirement") if i.data.get("traces_to")}
    branches = {e.parent for e in spec.elements.values() if e.parent}
    for item in spec.requirements():
        if item.id not in verified and not item.data.get("verification_deferred"):
            # CHECK-29: above the leaves, a requirement is met through its children or verified itself
            bare = item.kind != "constraint" and item.element in branches and item.id not in refined
            gap = "; nothing refines it either, so it's neither decomposed nor verified" if bare else " yet"
            out.append(_f("T004", f"{item.id} has no verification item{gap}", item.id, item))
    return out


def _flow_down(spec: Spec) -> list[Finding]:
    """CHECK-22: a requirement on an element refines a requirement of the element's parent (DR-58)."""
    out = []
    enforced = spec.config.get("flow_down") == "enforced"
    for item in spec.of_kind("requirement"):
        target = spec.items.get(str(item.data.get("traces_to") or ""))
        element = spec.elements.get(item.element)
        if item.data.get("derived") or target is None or element is None or not element.parent:
            continue  # untraced and legacy-derived requirements are T001's to report
        parent = spec.elements.get(element.parent)
        ok = target.element == element.parent and (target.kind == "requirement" or (
            parent is not None and not parent.parent and target.kind in ("system", "constraint")))
        if not ok:
            where = f"{target.element}'s" if target.kind == "requirement" else "the system's"
            out.append(Finding("T005", f"{item.id} is on {item.element}, whose parent is {element.parent}, but "
                                       f"refines {target.id}, one of {where} requirements", item.id, item.file,
                               item.line, level="error" if enforced else None))
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
        if origin is not None and origin not in ("engineer", "agent"):
            out.append(_f("A002", f"{item.id} has origin {origin!r}", item.id, item))
        elif origin is None and item.kind != "vi" and not item.data.get("intent") and not (
                item.kind != "need" and (item.data.get("basis") or review.history(spec, item.id))):
            out.append(_f("A002", f"{item.id} says neither who asked for it nor where it came from", item.id, item))
        if not item.data.get("text") and item.kind != "vi":
            out.append(_f("S007", f"{item.id} has no `text`", item.id, item))
    for item in spec.requirements():
        if not (item.data.get("why") or item.data.get("source") or item.data.get("quotes") or item.data.get("intent")):
            out.append(_f("A001", f"{item.id} has neither `why` nor `source`", item.id, item))
    for item in spec.items.values():
        out += _quote_findings(item)
        out += _intent_findings(item, item.data, item.id)
        basis = item.data.get("basis")
        if basis is not None and basis not in levels.ITEM_BASES:
            out.append(_f("A008", f"{item.id} has basis {basis!r}", item.id, item))
    for e in spec.elements.values():
        out += _intent_findings(e, e.data, e.id)
    if spec.version >= 2:  # DR-63: a migrated spec keeps no field of the older format
        from syseng import migrate
        for iid, found in migrate.legacy_items(spec):
            out.append(_f("A009", f"{iid} has {', '.join(f'`{f}`' for f in found)}", iid, spec.items[iid]))
        for a in spec.approvals:
            old = [k for k in ("words", "approved_at", "approved_on") if k in a]
            if old:
                out.append(Finding("A009", f"the lock on {a.get('id')} has {', '.join(f'`{k}`' for k in old)}",
                                   a.get("id"), spec.locks_path()))
                continue
            wrong = records.problems(records.Lock, a)
            if wrong:
                out.append(Finding("A010", f"the lock on {a.get('id')}: {'; '.join(wrong)}", a.get("id"),
                                   spec.locks_path()))
    for item in spec.of_kind("decision"):
        if item.data.get("decided_by") not in ("engineer", "agent"):
            out.append(_f("S007", f"{item.id} needs `decided_by: engineer` or `agent`", item.id, item))
        for f in ("title", "context", "decision"):
            if not item.data.get(f):
                out.append(_f("S007", f"{item.id} has no `{f}`", item.id, item))
    return out


def _quote_findings(item) -> list[Finding]:
    """Each quote keeps the engineer's exact words, when they said them, and what was being discussed (CHECK-20)."""
    quotes = item.data.get("quotes")
    if quotes is None:
        return []
    if not isinstance(quotes, list):
        return [_f("S007", f"{item.id}'s `quotes` must be a list", item.id, item)]
    out = []
    for n, q in enumerate(quotes, 1):
        missing = [k for k in ("words", "said", "context") if not (isinstance(q, dict) and q.get(k))]
        if missing:
            out.append(_f("S007", f"quote {n} on {item.id} has no `{'`, `'.join(missing)}`", item.id, item))
    return out


def _intent_findings(where, data: dict, iid: str) -> list[Finding]:
    """CHECK-20 and CHECK-25: each intent record is complete, and summarizes rather than quotes."""
    recs = data.get("intent")
    if recs is None:
        return []
    if not isinstance(recs, list):
        return [_f("A006", f"{iid}'s `intent` must be a list of records", iid, where)]
    out = []
    for n, r in enumerate(recs, 1):
        if not isinstance(r, dict):
            out.append(_f("A006", f"intent record {n} on {iid} isn't a mapping", iid, where))
            continue
        wrong = records.problems(records.IntentRecord, r)
        if wrong:
            out.append(_f("A006", f"intent record {n} on {iid}: {'; '.join(wrong)}", iid, where))
        for key in ("said", "context"):
            text = str(r.get(key) or "")
            for mark in ('"', "\u201c", "\u201d"):
                if mark in text:
                    at = text.index(mark)
                    out.append(Finding("A007", f"intent record {n} on {iid} has a double quotation mark in `{key}`",
                                       iid, where.file, where.line, text, (at, at + 1)))
                    break
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


def _test_links(spec: Spec) -> list[Finding]:
    """CHECK-4: each test a verification item links to exists, as a file and a test name in it."""
    roots = {i.get("name"): spec.repo_root() / str(i.get("root") or ".")
             for i in spec.config.get("implementations") or [] if isinstance(i, dict)}
    out, cache = [], {}
    for vi in spec.of_kind("vi"):
        tests = vi.data.get("tests") or {}
        if not isinstance(tests, dict):
            out.append(_f("V001", f"{vi.id}'s `tests` must map each implementation to a list of links", vi.id, vi))
            continue
        for impl, links in tests.items():
            if impl not in roots:
                out.append(_f("V002", f"{vi.id} links tests for {impl!r}, which toolkit.yaml doesn't name as an "
                                      f"implementation", vi.id, vi))
                continue
            for link in links or []:
                problem = testlinks.missing(roots[impl], str(link), cache)
                if problem:
                    out.append(_f("V002", f"{vi.id} links {link}, but {problem}", vi.id, vi))
    return out


# ---------------------------------------------------------------- approvals
def _approvals(spec: Spec) -> list[Finding]:
    out = []
    for a in spec.approvals:
        aid = a.get("id")
        if aid not in spec.items and aid not in spec.elements:
            out.append(Finding("A005", f"lock on {aid}, which doesn't exist", aid, spec.locks_path()))
    approvable = [(i.id, i.file, i.line) for i in spec.items.values()]
    approvable += [(e.id, e.file, 1) for e in spec.elements.values()]
    for iid, file, line in approvable:  # CHECK-19: what awaits a person is a change to what a person gave
        lv = levels.level_of(spec, iid)
        if lv.changed and not levels.seen_since(spec, levels.last_changed(spec, iid)):  # DR-68: until shown
            who = (lv.newest or {}).get("by")
            out.append(Finding("A003", f"{iid} changed since {who or 'a person'} {_verb(lv.given)} it", iid, file,
                               line))
    for cid, alt in review.unanswered(spec):
        out.append(Finding("A004", f"{alt['id']} was altered in {cid} ({', '.join(alt['reasons'])}) and awaits "
                                   f"the engineer's answer", alt["id"]))
    return out


def _verb(level: str) -> str:
    return {levels.EXPLICIT: "locked", levels.STATED: "stated", levels.GUIDED: "guided"}.get(level, "gave")


def _conflicts(spec: Spec) -> list[Finding]:
    """CHECK-26: before the open change is done, each alteration to an item a person locked or stated is either
    raised as a conflict, declared a rewording, or carries the person's own request for it."""
    from syseng import changes
    try:
        change = changes.current(spec)
    except changes.ChangeError:
        return []
    if change is None:
        return []
    named = {i for d in change.data.get("decisions") or [] for i in d.get("involves") or []}
    out = []
    for alt in review.alterations(spec, change):
        if alt["answered"] or alt["id"] in named:
            continue
        if all(e.get("rewording") or e.get("conflict") or e.get("requested") for e in alt["entries"]):
            continue
        logged = {e.get("level") for e in alt["entries"]} - {None}
        if logged and not logged & {levels.EXPLICIT, levels.STATED}:
            continue  # guided items are asked about once built, not raised as conflicts (DR-57)
        out.append(Finding("C001", f"{alt['id']} was altered in this change ({', '.join(alt['reasons'])}), and no "
                                   f"conflict names it", alt["id"]))
    return out


def _feedback(spec: Spec) -> list[Finding]:
    """CHECK-23: each comment from a person's feedback in the open change has a recorded response."""
    from syseng import changes, feedback
    try:
        waiting = feedback.unanswered(spec)
    except changes.ChangeError:
        return []
    return [Finding("F001", f"{f.get('n')} from {f.get('by')}" + (f" on {f['id']}" if f.get("id") else "")
                            + f" ({f.get('kind')}) has no response yet", f.get("id")) for _, f in waiting]


def approval_status(spec: Spec) -> list[dict]:
    """One entry per approvable item, with its review state (CHECK-18)."""
    rows = []
    approvable = [(i.id, i.kind, i.file, i.line) for i in spec.items.values()]
    approvable += [(e.id, "element", e.file, 1) for e in spec.elements.values()]
    for iid, kind, file, line in approvable:
        s = review.state_of(spec, iid)
        rows.append({"id": iid, "kind": kind, "state": s.state, "under": s.under, "file": file, "line": line,
                     "fingerprint": review.current_fingerprint(spec, iid)})
    return rows


# ---------------------------------------------------------------- rendered views
def _rendered(spec: Spec) -> list[Finding]:
    """Markdown views from before the review page: they show a spec that no longer exists (DR-60)."""
    return [Finding("R001", f"{p.relative_to(spec.root)} is a Markdown view the toolkit no longer generates", file=p)
            for p in render.stale_views(spec)]


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
            lines.append(f"   = rule: {rule.link(root)}")
        lines.append("")
    return "\n".join(lines)


def _n(count: int, noun: str) -> str:
    return f"{count} {noun}{'' if count == 1 else 's'}"


def summarize(findings: list[Finding]) -> str:
    errors = [f for f in findings if f.severity == "error"]
    todos = [f for f in findings if f.severity == "todo"]
    unverified = sum(1 for f in todos if f.code == "T004")
    changed = sum(1 for f in todos if f.code == "A003")
    flow = sum(1 for f in todos if f.code == "T005")
    unserved = sum(1 for f in todos if f.code == "T002")
    unanswered = sum(1 for f in todos if f.code == "A004")
    parts = [f"{len(errors)} error{'s' if len(errors) != 1 else ''}"]
    if todos:
        served = f"{_n(unserved, 'need')} nothing serves yet, " if unserved else ""
        answers = f"{_n(unanswered, 'alteration')} awaiting the engineer's answer, " if unanswered else ""
        changes_ = f", {_n(changed, 'item')} changed since a person gave it" if changed else ""
        flows = f", {_n(flow, 'requirement')} skipping a level of the breakdown" if flow else ""
        parts.append(f"{_n(len(todos), 'to-do')} ({answers}{served}{_n(unverified, 'requirement')} without "
                     f"verification items{changes_}{flows}; list them with `spec check --todo`)")
    return "spec check: " + ", ".join(parts)
