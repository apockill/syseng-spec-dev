"""How much human attention each item has had (SYS-33, SYS-34, SYS-37, SYS-39; DR-44).

Nothing here is stored. An item's review state is computed from the approvals and the trace
graph each time it's asked for, and the facts agents weigh are counted, never scored (SYS-40).

  approved    the engineer approved this exact content, explicitly or by restating it
  changed     the engineer approved an earlier version, and it has changed since
  delegated   not approved itself, but under an item that is approved: the agent's to decide
  unreviewed  nothing above it is approved either
"""

import re
from dataclasses import dataclass

from syseng import fingerprint
from syseng.model import Spec

APPROVED, CHANGED, DELEGATED, UNREVIEWED = "approved", "changed", "delegated", "unreviewed"


@dataclass
class State:
    state: str
    approval: dict | None = None  # approved: the record that matches; changed: the latest record
    under: str | None = None      # delegated: the nearest approved item above
    levels: int = 0               # delegated: how many levels up that item is


def kind_and_data(spec: Spec, iid: str) -> tuple[str, dict] | None:
    if iid in spec.items:
        return spec.items[iid].kind, spec.items[iid].data
    if iid in spec.elements:
        return "element", spec.elements[iid].data
    return None


def current_fingerprint(spec: Spec, iid: str) -> str | None:
    kd = kind_and_data(spec, iid)
    return fingerprint.of(*kd) if kd else None


def history(spec: Spec, iid: str) -> list[dict]:
    """Every approval of an item, oldest first (MODEL-35)."""
    return [a for a in spec.approvals if a.get("id") == iid]


def _own_state(spec: Spec, iid: str) -> State | None:
    records = history(spec, iid)
    if not records:
        return None
    now = current_fingerprint(spec, iid)
    matching = [a for a in records if a.get("fingerprint") == now]
    return State(APPROVED, matching[-1]) if matching else State(CHANGED, records[-1])


def parents(spec: Spec, iid: str) -> list[str]:
    """The items directly above one in the trace graph (CHECK-18)."""
    if iid in spec.elements:
        parent = spec.elements[iid].parent
        return [parent] if parent else []
    item = spec.items.get(iid)
    if item is None:
        return []
    d = item.data
    if item.kind in ("system", "constraint"):
        return list(d.get("serves") or [])
    if item.kind == "requirement":
        return [d["traces_to"]] if d.get("traces_to") else []
    if item.kind == "vi":
        return list(d.get("verifies") or [])
    if item.kind == "decision":
        return re.findall(r"\b(?:[A-Z]+-V?\d+)\b", str(d.get("requirements") or ""))
    return []


def state_of(spec: Spec, iid: str) -> State:
    own = _own_state(spec, iid)
    if own is not None:
        return own
    frontier, seen, level = [iid], {iid}, 0
    while frontier:
        level += 1
        above = [p for f in frontier for p in parents(spec, f) if p not in seen]
        for p in above:
            s = _own_state(spec, p)
            if s is not None and s.state == APPROVED:
                return State(DELEGATED, under=p, levels=level)
        seen.update(above)
        frontier = above
    return State(UNREVIEWED)


def engineer_marks(spec: Spec, iid: str) -> list[str]:
    """Why an item counts as approved, written or decided by the engineer (CHANGE-13)."""
    out = []
    if history(spec, iid):
        out.append("you approved it")
    kd = kind_and_data(spec, iid)
    data = kd[1] if kd else {}
    if data.get("origin") == "engineer" or data.get("quotes"):
        out.append("it carries your words")
    if kd and kd[0] == "decision" and data.get("decided_by") == "engineer":
        out.append("you decided it")
    return out


# ---------------------------------------------------------------- the facts agents weigh (SYS-39)

def _edits(spec: Spec, iid: str) -> list[tuple[str, dict]]:
    from syseng import changes  # changes imports render, which imports this module
    return [(c.id, e) for c in changes.all_changes(spec) for e in c.data.get("entries") or [] if e.get("id") == iid]


def _discussions(spec: Spec, iid: str) -> list[str]:
    from syseng import changes
    out = [f"{c.id} {d.get('id')}" for c in changes.all_changes(spec) for d in c.data.get("decisions") or []
           if iid in (d.get("involves") or [])]
    out += [x.id for x in spec.of_kind("decision") if iid in parents(spec, x.id)]
    return out


def links_to(spec: Spec, iid: str) -> int:
    """How many items point at this one: refinements, verification items, decision records, elements."""
    count = sum(1 for other in list(spec.items) + list(spec.elements) if other != iid and iid in parents(spec, other))
    return count


def describe(spec: Spec, iid: str) -> str:
    """One line of attention facts, for an agent about to change the item (CLI-13)."""
    s = state_of(spec, iid)
    parts = []
    if s.state in (APPROVED, CHANGED):
        a = s.approval or {}
        when = a.get("approved_at") or a.get("approved_on") or "an unknown date"
        how = a.get("via") or "an unrecorded channel"
        batch = a.get("batch")
        alone = "alone" if batch == 1 else f"with {batch - 1} other items" if batch else ""
        approved = f"approved {when} via {how}" + (f", {alone}" if alone else "")
        n = len(history(spec, iid))
        if n > 1:
            approved += f" ({n} approvals in all)"
        parts.append(approved if s.state == APPROVED else f"changed since it was {approved}")
    elif s.state == DELEGATED:
        parts.append(f"delegated under {s.under}" + (f", {s.levels} levels up" if s.levels > 1 else ""))
    else:
        parts.append("unreviewed: nothing above it is approved")
    kd = kind_and_data(spec, iid)
    data = kd[1] if kd else {}
    words = len(data.get("quotes") or []) or (1 if data.get("origin") == "engineer" and data.get("source") else 0)
    if words:
        parts.append("carries your words")
    if kd and kd[0] == "decision" and data.get("decided_by") == "engineer":
        parts.append("your decision")
    edits = _edits(spec, iid)
    if edits:
        cid, entry = edits[-1]
        last = entry.get("at") or f"in {cid}"  # entries logged before timestamps name their change
        parts.append(f"edited {len(edits)} time{'s' if len(edits) != 1 else ''}, last {last}")
    talks = _discussions(spec, iid)
    if talks:
        parts.append(f"discussed in {', '.join(talks)}")
    n = links_to(spec, iid)
    if n:
        parts.append(f"{n} item{'s link' if n != 1 else ' links'} to it")
    return "; ".join(parts)


# ---------------------------------------------------------------- alterations to answer (SYS-37)

def alterations(spec: Spec, change) -> list[dict]:
    """The alterations one change made to items the engineer approved, wrote or decided, one per item.

    An alteration is answered once the engineer approves the item as it now is (kept), or once the
    item is back to what it was before the change (rolled back) (CHANGE-14)."""
    by_item: dict[str, list[dict]] = {}
    for e in change.data.get("entries") or []:
        if e.get("raised"):
            by_item.setdefault(e["id"], []).append(e)
    out = []
    for iid, entries in by_item.items():
        exists = kind_and_data(spec, iid) is not None
        rolled_back = exists and current_fingerprint(spec, iid) == entries[0].get("fingerprint_before")
        kept = exists and state_of(spec, iid).state == APPROVED
        out.append({"id": iid, "reasons": entries[0]["raised"], "entries": entries, "removed": not exists,
                    "answered": kept or rolled_back, "rolled_back": rolled_back})
    return out


def unanswered(spec: Spec) -> list[tuple[str, dict]]:
    """Every alteration, in every change, that still awaits the engineer's answer (CHECK-21)."""
    from syseng import changes
    return [(c.id, a) for c in changes.all_changes(spec) for a in alterations(spec, c)
            if not a["answered"] and not a["removed"]]
