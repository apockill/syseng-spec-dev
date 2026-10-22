"""Everything the review page shows, built as data (SYS-45, SYS-47, DR-59).

The review page embeds what `build` returns and renders it; `spec review --section` prints the same
sections as text or YAML, so an agent can answer from exactly what the person is looking at.

Sections, in the page's order (REVIEW-20):
  awaiting    open decisions (conflicts first) and alterations waiting for the person
  responses   the agent's responses to the person's last feedback
  changes     differences since the person's last review, and against each other version named
  captured    intent recorded from what people said since then, to correct or remove (REVIEW-25)
  proposals   the items most worth locking, each with its reason
  graph       the system breakdown with every item in it, for the graph
  items       the full spec
"""

import datetime
import hashlib
import subprocess
from pathlib import Path

from syseng import changes, diff, health, levels, review
from syseng.model import Spec

SECTIONS = ("overview", "awaiting", "responses", "changes", "captured", "proposals", "graph", "items")


def _git(repo: Path, *args: str) -> str:
    try:
        run = subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True, timeout=30)
        return run.stdout.strip() if run.returncode == 0 else ""
    except (OSError, subprocess.TimeoutExpired):
        return ""


def decision_fingerprint(d: dict) -> str:
    """What a person saw of a decision: its question and options. A choice made on an older version is stale."""
    text = d.get("question", "") + "\n" + "\n".join(f"{o.get('label', '')}: {o.get('detail', '')}"
                                                   for o in d.get("options") or [])
    return hashlib.sha256(text.encode()).hexdigest()[:12]


# ---------------------------------------------------------------- items
def _item(spec: Spec, iid: str) -> dict:
    kind, data = review.kind_and_data(spec, iid)
    lv = levels.level_of(spec, iid)
    item = spec.items.get(iid)
    out = {
        "id": iid, "kind": kind, "element": item.element if item else iid,
        "text": str(data.get("text") or data.get("description") or data.get("purpose") or ""),
        "title": str(data.get("title") or ""),
        "level": lv.level, "changed": lv.changed, "under": lv.under, "given": lv.given, "label": levels.label(lv),
        "parents": review.parents(spec, iid),
        "fingerprint": review.current_fingerprint(spec, iid),
        "intent": levels.intent_records(data),
        "locks": [{k: a.get(k) for k in ("locked_at", "approved_at", "approved_on", "by", "via", "batch", "said")
                   if a.get(k) is not None} for a in review.history(spec, iid)],
    }
    for key in ("why", "basis", "decided_by", "status", "context", "decision", "alternatives", "consequences",
                "method", "technique", "verifies", "depends_on", "parent", "requirements"):
        if data.get(key) not in (None, "", []):
            out[key] = data[key]
    return out


def items(spec: Spec) -> dict:
    ids = list(spec.elements) + list(spec.items)
    return {i: _item(spec, i) for i in ids}


def graph(spec: Spec) -> dict:
    """The system breakdown: elements as a tree, each with its items, and the links between them (REVIEW-21)."""
    order = spec.element_order()
    elements = []
    for eid in order:
        e = spec.elements[eid]
        own = [i.id for i in spec.items.values() if i.element == eid]
        depth, cur = 0, e
        while cur.parent and cur.parent in spec.elements:
            depth, cur = depth + 1, spec.elements[cur.parent]
        elements.append({"id": eid, "title": e.title, "parent": e.parent, "depends_on": e.depends_on, "depth": depth,
                         "items": sorted(own, key=_sort_key(spec))})
    return {"elements": _tree_order(elements)}


def _sort_key(spec: Spec):
    rank = {"need": 0, "system": 1, "constraint": 2, "requirement": 3, "decision": 4, "vi": 5}

    def key(iid):
        head, _, num = iid.rpartition("-")
        return (rank.get(spec.items[iid].kind, 9), head, int(num.lstrip("V")) if num.lstrip("V").isdigit() else 0)
    return key


def _tree_order(elements: list[dict]) -> list[dict]:
    """Depth-first, so each element follows its parent, in the configured order among siblings."""
    by_parent: dict = {}
    for e in elements:
        by_parent.setdefault(e["parent"], []).append(e)
    out = []

    def walk(parent):
        for e in by_parent.get(parent, []):
            out.append(e)
            walk(e["id"])
    walk(None)
    return out + [e for e in elements if e not in out]


# ---------------------------------------------------------------- what awaits the person
def awaiting(spec: Spec) -> dict:
    decisions = []
    for c in changes.all_changes(spec):
        for d in c.data.get("decisions") or []:
            if d.get("status") == "open":
                decisions.append({"change": c.id, **{k: d.get(k) for k in ("id", "kind", "question", "importance",
                                                                           "involves", "options")},
                                  "fingerprint": decision_fingerprint(d)})
    decisions.sort(key=lambda d: d.get("kind") != "conflict")  # conflicts first (SYS-49)
    alterations = []
    for cid, alt in review.unanswered(spec):
        alterations.append({"change": cid, "id": alt["id"], "reasons": alt["reasons"],
                            "fingerprint": review.current_fingerprint(spec, alt["id"]),
                            "entries": [{k: e.get(k) for k in ("reason", "before", "after", "at", "rewording")
                                         if e.get(k) is not None} for e in alt["entries"]]})
    return {"decisions": decisions, "alterations": alterations}


def responses(spec: Spec, person: str) -> list[dict]:
    """Each comment from the person's feedback, with the agent's response (SYS-52, CHANGE-19)."""
    out = []
    for c in changes.all_changes(spec):
        for f in c.data.get("feedback") or []:
            if f.get("by") == person and f.get("comment"):
                out.append({"change": c.id, **f})
    return out[-30:]


# ---------------------------------------------------------------- what changed
def change_sets(spec: Spec, person: str, against: list[str]) -> list[dict]:
    out = []
    try:
        first = diff.since_review(spec, person, inspect=health.metrics)
    except diff.DiffError:
        try:
            first = diff.between(spec, "HEAD", inspect=health.metrics)
            first.older.note = (first.older.note + "; " if first.older.note else "") + "no review sent back yet"
        except diff.DiffError:
            first = None
    for d in [first] + [_safe_between(spec, a) for a in against]:
        if d is not None:
            out.append({**d.to_data(), "measured": d.inspected})
    return out


def overview(spec: Spec, person: str, sets: list[dict]) -> dict:
    """The spec's numbers now and at the person's last review, with what changed between (REVIEW-32)."""
    now = health.metrics(spec)
    first = sets[0] if sets else None
    was, source = None, None
    last = diff.last_review(spec, person)
    if last:  # what the person's last page showed, when this machine kept it
        import json
        snap = spec.repo_root() / ".syseng" / "reviews" / f"{last.get('review')}.json"
        if snap.exists():
            was = (json.loads(snap.read_text()).get("overview") or {}).get("now")
            source = "what your last review page showed"
    if was is None and first:
        was, source = first.get("measured"), f"the spec at {first['older']['label']}"
    return {"now": now, "was": was, "against": source, "measures": health.compare(now, was),
            "changes": first["counts"] if first else {}, "by_kind": first.get("by_kind", {}) if first else {},
            "since": first["older"]["label"] if first else None}


def _safe_between(spec: Spec, label: str):
    try:
        return diff.between(spec, label)
    except diff.DiffError:
        return None


def captured(spec: Spec, sets: list[dict]) -> list[dict]:
    """Intent recorded since the person's last review: each record new on the newer side (REVIEW-25)."""
    out = []
    if not sets:
        return out
    for d in sets[0]["items"]:
        before = d.get("before", {}).get("intent") or []
        after = d.get("after", {}).get("intent") or []
        for n, rec in enumerate(after):
            if rec not in before:
                out.append({"id": d["id"], "index": n, "record": rec})
    return out


# ---------------------------------------------------------------- worth locking
def proposals(spec: Spec, limit: int = 5) -> list[dict]:
    """The items most worth locking: the agents' proposals first, then the most-depended-on items a person gave but
    hasn't locked, each with its reason (SYS-38, AGENT-40)."""
    latest: dict[str, dict] = {}  # an item proposed again shows with its newest proposal, oldest first (REVIEW-36)
    for c in changes.all_changes(spec):
        for p in c.data.get("proposals") or []:
            for iid in p.get("ids") or []:
                if review.kind_and_data(spec, iid) is None or levels.level_of(spec, iid).level == levels.EXPLICIT:
                    continue
                latest.pop(iid, None)
                latest[iid] = {"id": iid, "why": p.get("why", ""), "from": "an agent's proposal", "change": c.id}
    out, seen = list(latest.values()), set(latest)
    below = _beneath(spec)
    candidates = []
    for iid in list(spec.items):
        lv = levels.level_of(spec, iid)
        if iid in seen or lv.level not in (levels.STATED, levels.GUIDED) or spec.items[iid].kind == "vi":
            continue
        n = len(below.get(iid, ()))
        if n:
            candidates.append((n, iid, lv.level))
    for n, iid, level in sorted(candidates, key=lambda c: (-c[0], c[1]))[:limit]:
        out.append({"id": iid, "from": "computed",
                    "why": f"{n} item{'s' if n != 1 else ''} sit beneath it, and a person {level} it but hasn't locked "
                           f"it: locking it puts that part of the tree on record as theirs."})
    return out


def _beneath(spec: Spec) -> dict[str, set[str]]:
    kids: dict[str, set[str]] = {}
    for iid in list(spec.items) + list(spec.elements):
        for p in review.parents(spec, iid):
            kids.setdefault(p, set()).add(iid)
    out: dict[str, set[str]] = {}

    def collect(i, seen):
        for k in kids.get(i, ()):
            if k not in seen:
                seen.add(k)
                collect(k, seen)
        return seen
    for i in kids:
        out[i] = collect(i, set())
    return out


# ---------------------------------------------------------------- everything
def build(spec: Spec, person: str, against: list[str] | None = None) -> dict:
    repo = spec.repo_root()
    revision = _git(repo, "rev-parse", "HEAD")
    dirty = bool(_git(repo, "status", "--porcelain", "--", str(spec.root)))
    now = datetime.datetime.now().astimezone().isoformat(timespec="minutes")
    sets = change_sets(spec, person, against or [])
    data = {
        "meta": {"review": hashlib.sha256(f"{revision}{now}{person}".encode()).hexdigest()[:10], "person": person,
                 "generated": now, "revision": revision, "dirty": dirty, "repository": repo.name,
                 "levels": list(levels.ORDER),
                 "applied": [r.get("review") for r in levels.reviews(spec) if r.get("by") == person]},
        "overview": overview(spec, person, sets),
        "awaiting": awaiting(spec),
        "responses": responses(spec, person),
        "changes": sets,
        "captured": captured(spec, sets),
        "proposals": proposals(spec),
        "graph": graph(spec),
        "items": items(spec),
    }
    return data


# ---------------------------------------------------------------- text, for agents (CLI-24)
def _label(data: dict, iid: str) -> str:
    it = data["items"].get(iid) or {}
    text = it.get("title") or it.get("text") or ""
    words = text.split()
    return f"{iid} ({' '.join(words[:9])}{'…' if len(words) > 9 else ''})" if words else iid


def section_text(data: dict, name: str) -> str:
    lines: list[str] = []
    if name == "overview":
        o = data["overview"]
        if o["since"]:
            lines.append(f"since {o['since']}: " + (", ".join(f"{n} {diff.CLASS_WORDS.get(c, c)}" for c, n in o["changes"].items())
                                                     or "no differences"))
        for m in o["measures"]:
            delta = "" if m["delta"] in (None, 0) else f" ({'+' if m['delta'] > 0 else ''}{m['delta']}{'%' if m['percent'] else ''})"
            mark = " WORSE" if m["worse"] else " better" if m["improved"] else ""
            lines.append(f"  {m['label']}: {m['now']}{'%' if m['percent'] else ''}{delta}{mark}")
        lines.append("  intent mix: " + ", ".join(f"{n} {k}" for k, n in o["now"]["mix"].items()))
    elif name == "awaiting":
        for d in data["awaiting"]["decisions"]:
            lines.append(f"{'CONFLICT ' if d.get('kind') == 'conflict' else ''}{d['change']} {d['id']}: {d['question']}")
            if d.get("involves"):
                lines.append("  involves: " + "; ".join(_label(data, i) for i in d["involves"]))
            for n, o in enumerate(d.get("options") or [], 1):
                lines.append(f"  {n}. {o.get('label')}{' (recommended)' if o.get('recommended') else ''}")
        for a in data["awaiting"]["alterations"]:
            lines.append(f"ALTERATION {_label(data, a['id'])} in {a['change']}: {', '.join(a['reasons'])}")
            for e in a["entries"]:
                lines.append(f"  why: {e.get('reason', '')}")
    elif name == "responses":
        for r in data["responses"]:
            lines.append(f"{r.get('id') or 'general'}: {r.get('comment')}")
            lines.append(f"  response: {r.get('response') or '(none yet)'}")
    elif name == "changes":
        for d in data["changes"]:
            lines.append(f"{d['older']['label']} → {d['newer']['label']}: "
                         + (", ".join(f"{n} {diff.CLASS_WORDS.get(c, c)}" for c, n in d["counts"].items())
                            or "no differences"))
            for it in d["items"][:200]:
                lines.append(f"  {it['id']} [{', '.join(it['classes'])}] {it.get('title', '')[:120]}")
    elif name == "captured":
        for c in data["captured"]:
            r = c["record"]
            lines.append(f"{_label(data, c['id'])}: {r.get('basis')} by {r.get('by')}, {r.get('when')}: {r.get('said')}")
    elif name == "proposals":
        for p in data["proposals"]:
            lines.append(f"{_label(data, p['id'])}: {p['why']} [{p['from']}]")
    elif name == "graph":
        for e in data["graph"]["elements"]:
            lv = {}
            for i in e["items"]:
                lv[data["items"][i]["level"]] = lv.get(data["items"][i]["level"], 0) + 1
            counts = ", ".join(f"{n} {k}" for k, n in sorted(lv.items(), key=lambda kv: levels.ORDER.index(kv[0])))
            lines.append(f"{'  ' * e['depth']}{e['id']}: {e['title']} ({counts or 'no items'})"
                         + (f"; uses {', '.join(e['depends_on'])}" if e["depends_on"] else ""))
    elif name == "items":
        for iid, it in data["items"].items():
            lines.append(f"{iid} [{it['level']}{', changed' if it['changed'] else ''}] {it.get('title') or it['text']}")
    return "\n".join(lines) + ("\n" if lines else "nothing here\n")
