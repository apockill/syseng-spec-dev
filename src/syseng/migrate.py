"""Moves a spec to the current format, spec_version 2: intent records and locks (DR-61, DR-63).

What needs judgment comes first, from an agent, through `spec edit`: each item's verbatim words
become intent records, and an agent's items get a basis. Then `spec migrate`, in the same open
change, does the rest mechanically:

  - carries each lock over an item that the change only reworded (declared `rewording: true`),
    keeping the old fingerprint as `migrated_from`, as an earlier migration did (DR-29);
  - moves approvals.yaml to locks.yaml, with `locked_at` and without the person's words;
  - takes the verbatim words out of every change record's logged before and after values and
    out of resolved decisions, leaving a marker;
  - sets spec_version 2, and enforces flow-down when nothing violates it.

It refuses while any item still has a field of the older format, and it runs once.
"""

from syseng import check, fingerprint, levels, review, yamlio
from syseng.model import Spec

LEGACY_FIELDS = ("source", "quotes", "origin", "refines", "derived")
SCRUBBED_KEYS = ("source", "quotes", "refines", "words")
MARKER = "[verbatim words removed when this spec moved to intent records]"


class MigrateError(Exception):
    pass


def _verbatim(value) -> bool:
    """Whether a logged value may hold a person's exact words. Values written as summaries say so."""
    return value != MARKER and "(summary)" not in str(value)


def legacy_items(spec: Spec) -> list[tuple[str, list[str]]]:
    """Items that still have a field of the older format, with those fields."""
    out = []
    for item in spec.items.values():
        found = [f for f in LEGACY_FIELDS if f in item.data]
        if found:
            out.append((item.id, found))
    return out


def run(spec: Spec, change, dry_run: bool = False) -> dict:
    if spec.version >= 2:
        raise MigrateError("this spec is already in the current format (spec_version 2)")
    if change is None:
        raise MigrateError("open the change the migration belongs to first, with `spec change start`")
    remaining = legacy_items(spec)
    if remaining:
        listed = "; ".join(f"{i} ({', '.join(f)})" for i, f in remaining[:12])
        more = f", and {len(remaining) - 12} more" if len(remaining) > 12 else ""
        raise MigrateError(
            f"{len(remaining)} items still have fields of the older format: {listed}{more}. Convert them first with "
            "`spec edit`: a person's words become `intent:` records (summarized, never quoted) and the old fields are "
            "unset; an agent's items get `basis: derived` or `basis: added`.")
    report = {"carried": _carry_rewordings(spec, change, dry_run)}
    report.update(_move_locks(spec, dry_run))
    report["scrubbed"] = _scrub_changes(spec, change, dry_run)
    report["legacy_records"] = _remove_legacy_records(spec, dry_run)
    report["flow_down"] = "enforced" if not any(f.code == "T005" for f in check.check(spec)) else "to-do"
    if not dry_run:
        config = dict(spec.config, spec_version=2)
        if report["flow_down"] == "enforced":
            config["flow_down"] = "enforced"
        yamlio.write(spec.root / "toolkit.yaml", config)
        change.data.setdefault("migrations", []).append({"to": "spec_version 2", **report})
        change.save()
    return report


def _carry_rewordings(spec: Spec, change, dry_run: bool) -> list[str]:
    """Locks on items this change only reworded follow the new wording (DR-63)."""
    entries: dict[str, list[dict]] = {}
    for e in change.data.get("entries") or []:
        if e.get("fingerprint_before"):
            entries.setdefault(e["id"], []).append(e)
    locks = list(spec.approvals)
    carried = []
    for iid, es in entries.items():
        now = review.current_fingerprint(spec, iid)
        if not all(e.get("rewording") for e in es) or es[-1].get("fingerprint_after") != now:
            continue
        old = es[0]["fingerprint_before"]
        matching = [a for a in locks if a.get("id") == iid and a.get("fingerprint") == old]
        if not matching:
            continue
        kind, data = review.kind_and_data(spec, iid)
        for a in matching:
            a["migrated_from"] = old
            a["fingerprint"] = now
            a["text"] = fingerprint.summary(kind, data)
        carried.append(iid)
    if carried and not dry_run:
        yamlio.write(spec.locks_path(), locks)
    return carried


def _move_locks(spec: Spec, dry_run: bool) -> dict:
    """approvals.yaml becomes locks.yaml, each record fitting the Lock schema, without the person's words."""
    import re
    from syseng import people, records
    person, _ = people.person(spec.repo_root())
    name = person.split(" <")[0]
    words, filled = 0, 0
    out = []
    for a in spec.approvals:
        rec = {"id": a.get("id"), "fingerprint": a.get("fingerprint"),
               "locked_at": str(a.get("locked_at") or a.get("approved_at") or a.get("approved_on") or "")}
        notes = [str(a["note"])] if a.get("note") else []
        via = str(a.get("via") or "")
        m = re.match(r"^(\w+)\s*(?:\((.*)\))?$", via)
        how, detail = (m.group(1), m.group(2)) if m else (via, None)
        if detail and "menu" in detail.split(",")[0]:
            how, detail = "menu", ", ".join(p.strip() for p in detail.split(",")[1:]) or None
        rec["via"] = how if how in records.CHANNELS else "chat"
        if detail or how not in records.CHANNELS:
            notes.append(f"given via {via}")
        by = str(a.get("by") or "")
        if not records.PERSON.match(by):
            if by in ("", name):  # earlier records named no one, or only a name: the person migrating
                notes.append("approver not recorded with an email address; the migration filled in the person running "
                             "it" if by else "approver not recorded; the migration filled in the person running it")
                by = person
                filled += 1
        rec["by"] = by
        for key in ("batch", "after", "text", "migrated_from"):
            if a.get(key) is not None:
                rec[key] = a[key]
        if notes:
            rec["note"] = "; ".join(notes)
        words += 1 if a.get("words") else 0
        out.append(rec)
    out.sort(key=lambda a: (str(a.get("id")), levels.when(a)))
    if not dry_run:
        yamlio.write(spec.root / "locks.yaml", out)
        old = spec.root / "approvals.yaml"
        if old.exists():
            old.unlink()
    return {"locks": len(out), "words_removed": words, "people_filled_in": filled}


def _remove_legacy_records(spec: Spec, dry_run: bool) -> list[str]:
    """Hand-written change records from before records were YAML: their verbatim words leave the current tree,
    and version control keeps them (DR-65)."""
    legacy = sorted(p for p in (spec.root / "changes").glob("*.md") if not p.with_suffix(".yaml").exists())
    if not dry_run:
        for p in legacy:
            p.unlink()
    return [p.name for p in legacy]


def _scrub_changes(spec: Spec, open_change, dry_run: bool) -> int:
    """Verbatim words out of every change record's history: logged values and resolved decisions."""
    from syseng import changes
    count = 0
    for c in changes.all_changes(spec):
        data = open_change.data if c.path == open_change.path else c.data
        touched = 0
        for e in data.get("entries") or []:
            for side in ("before", "after"):
                values = e.get(side) or {}
                for key in SCRUBBED_KEYS:
                    if key in values and _verbatim(values[key]):
                        values[key] = MARKER
                        touched += 1
        for d in data.get("decisions") or []:
            if d.get("words") and _verbatim(d["words"]):
                d["words"] = MARKER
                touched += 1
        if touched and not dry_run and c.path != open_change.path:
            yamlio.write(c.path, data)
        count += touched
    return count
