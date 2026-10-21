"""Editing the spec through the CLI.

An edit is a batch of operations, sent as one YAML document:

    edits:
      - add: requirement            # need | requirement | system | constraint | vi | decision | element
        element: CLI                # where it goes (not needed for needs, system requirements, constraints)
        text: The CLI shall …       # plus the kind's other fields; `id` is allocated when omitted
        reason: why this is added   # every operation needs a reason
      - modify: CLI-3
        set: {text: …}              # fields to set; `unset: [field]` removes fields
        reason: …
      - remove: CLI-9
        reason: …
    acks:                           # one note per affected item, when the CLI asks for them
      CLI-V1: still verifies the new wording

What a person asked for goes on the item as intent, summarized, never quoted. On an add or a
modify, `intent:` appends records; `by`, `when` and the fingerprint are filled in:

      - modify: CLI-3
        set: {text: …}
        intent: {basis: stated, context: what was being discussed, said: what they asked for, in summary}
        reason: …

An item no person asked for says where it came from instead: `basis: derived` (something above
needs it) or `basis: added` (an agent's own idea). Two more keys answer for a change to an item a
person locked or stated: `rewording: true` when the meaning stays, or `conflict: D2`, the
resolved conflict that allows it.

The batch runs against a scratch copy first. The CLI shows each operation's context,
asks for acknowledgments only where an approved or depended-on item is affected, and
rejects the batch if it would introduce checker errors. Only then does it write the spec and
log every operation, with its reason, in the open change record.
"""

import copy
import datetime
import difflib
import hashlib
import re
import shutil
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from syseng import changes, check, fingerprint, levels, model, people, records, render, review, yamlio
from syseng.model import Spec

KIND_FILES = {"need": "needs.yaml", "requirement": "requirements.yaml", "system": "requirements.yaml",
              "constraint": "requirements.yaml", "vi": "verification.yaml", "decision": "decisions.yaml"}
FIELDS = {
    "need": {"text", "origin", "source", "quotes", "context", "intent"},
    "requirement": {"text", "origin", "traces_to", "derived", "why", "source", "quotes", "refines", "reworded",
                    "allocation_note", "verification_deferred", "intent", "basis"},
    "system": {"kind", "text", "origin", "serves", "why", "source", "quotes", "refines", "reworded",
               "allocation_note", "verification_deferred", "intent", "basis"},
    "vi": {"verifies", "method", "technique", "description", "origin", "tests", "intent"},
    "decision": {"title", "decided_by", "elements", "requirements", "recorded", "status", "context",
                 "decision", "alternatives", "consequences", "intent", "basis"},
    "element": {"title", "parent", "depends_on", "purpose", "related_code", "note", "intent"},
}
FIELDS["constraint"] = FIELDS["system"]


class EditError(Exception):
    pass


@dataclass
class Op:
    op: str
    kind: str
    id: str | None
    element: str | None
    fields: dict
    unset: list
    reason: str
    intent: list = field(default_factory=list)  # records to append, before `by`, `when` and fingerprint are filled
    rewording: bool = False                     # the text changes, the meaning doesn't (DR-57)
    conflict: str | None = None                 # the conflict that allows changing a locked or stated item

    @property
    def requested(self) -> bool:
        """Carries a person's request for the change itself (CLI-22)."""
        return any(r.get("basis") == "stated" for r in self.intent)


@dataclass
class Result:
    applied: bool = False
    needs_acks: dict[str, str] = field(default_factory=dict)  # id -> why it's affected
    context: list[str] = field(default_factory=list)
    errors: list[check.Finding] = field(default_factory=list)
    ids: list[str] = field(default_factory=list)


# ---------------------------------------------------------------- parsing
def parse(doc) -> tuple[list[Op], dict]:
    if isinstance(doc, list):
        raw_ops, acks = doc, {}
    elif isinstance(doc, dict):
        raw_ops, acks = doc.get("edits") or [], doc.get("acks") or {}
    else:
        raise EditError("send a YAML list of operations, or a mapping with `edits:` (and `acks:`)")
    if not raw_ops:
        raise EditError("no operations to apply")
    ops = []
    for n, raw in enumerate(raw_ops, 1):
        if not isinstance(raw, dict):
            raise EditError(f"operation {n} must be a mapping")
        verbs = [v for v in ("add", "modify", "remove") if v in raw]
        if len(verbs) != 1:
            raise EditError(f"operation {n} needs exactly one of `add`, `modify` or `remove`")
        verb = verbs[0]
        reason = raw.get("reason")
        intent = _intent_list(raw.get("intent"), n) if verb != "remove" else []
        extra = {"intent": intent, "rewording": bool(raw.get("rewording")),
                 "conflict": str(raw["conflict"]) if raw.get("conflict") else None}
        if not reason:  # CLI-8, CHANGE-5
            target = raw.get(verb)
            raise EditError(f"operation {n} ({verb} {target}) has no `reason`. Every change to the spec records "
                            "why it was made, so the engineer can ask later.")
        if verb == "add":
            kind = raw["add"]
            if kind not in FIELDS:
                raise EditError(f"operation {n}: can't add {kind!r}; use one of {', '.join(FIELDS)}")
            fields = {k: v for k, v in raw.items()
                      if k not in ("add", "element", "reason", "id", "intent", "rewording", "conflict")}
            ops.append(Op("add", kind, raw.get("id"), raw.get("element"), fields, [], reason, **extra))
        else:
            fields = raw.get("set") or {}
            unset = raw.get("unset") or []
            if verb == "modify" and not fields and not unset and not intent:
                raise EditError(f"operation {n} (modify {raw['modify']}) sets nothing; use `set:`, `unset:` or "
                                "`intent:`")
            ops.append(Op(verb, "", str(raw[verb]), None, fields, unset, reason, **extra))
    return ops, {str(k): str(v) for k, v in acks.items()}


def _intent_list(value, n: int) -> list[dict]:
    if value is None:
        return []
    recs = value if isinstance(value, list) else [value]
    for r in recs:
        wrong = records.problems(records.IntentDraft, r) if isinstance(r, dict) else ["isn't a mapping"]
        if wrong:
            raise EditError(f"operation {n}: intent record: {'; '.join(wrong)}. A record has basis (stated: what the "
                            "person said, taken alone, says what the item requires; guided: their choice or "
                            "constraint fixed it), context, said, and optionally by and when.")
    return [dict(r) for r in recs]


# ---------------------------------------------------------------- applying to a directory
def _next_id(spec: Spec, prefix: str) -> str:
    taken = set(spec.items) | set(spec.elements) | spec.retired_ids()
    nums = [int(i[len(prefix):]) for i in taken if i.startswith(prefix) and i[len(prefix):].isdigit()]
    return f"{prefix}{max(nums + [0]) + 1}"


def _root_id(spec: Spec) -> str:
    roots = [e.id for e in spec.elements.values() if not e.parent]
    if len(roots) != 1:
        raise EditError("the spec needs exactly one root system element before items can be added")
    return roots[0]


def _check_fields(kind: str, keys, where: str) -> None:
    for k in keys:
        if k not in FIELDS[kind]:
            close = difflib.get_close_matches(k, FIELDS[kind], n=1)
            hint = f" Did you mean `{close[0]}`?" if close else f" Known fields: {', '.join(sorted(FIELDS[kind]))}."
            raise EditError(f"{where}: unknown field `{k}` for a {kind}.{hint}")


def apply_ops(root: Path, ops: list[Op], change_id: str, person: str = "", now: str = "") -> list[str]:
    """Applies operations to the spec files under `root`. Returns the IDs touched, in order."""
    ids = []
    for op in ops:
        spec = model.load(root)
        if op.op == "add":
            ids.append(_add(spec, root, op))
        elif op.op == "modify":
            ids.append(_modify(spec, op))
        else:
            ids.append(_remove(spec, root, op, change_id))
    pending = {i: op.intent for op, i in zip(ops, ids) if op.intent}
    if pending:  # each record is stamped with the item as it stands after the whole batch
        spec = model.load(root)
        for iid, recs in pending.items():
            full = [{"by": r.get("by") or person, "when": r.get("when") or now, "context": r.get("context"),
                     "said": r.get("said"), "basis": r.get("basis"), "fingerprint": _fingerprint(spec, iid)}
                    for r in recs]
            for rec in full:
                wrong = records.problems(records.IntentRecord, rec)
                if wrong:
                    raise EditError(f"intent on {iid}: {'; '.join(wrong)}. The person comes from "
                                    f"`git config {people.SETTING} \"Name <email>\"` unless the record names one.")
            _append_intent(spec, iid, full)
    return ids


def _append_intent(spec: Spec, iid: str, recs: list[dict]) -> None:
    if iid in spec.elements:
        element = spec.elements[iid]
        yamlio.write(element.file, {**element.data, "intent": [*(element.data.get("intent") or []), *recs]})
        return
    item = spec.items[iid]
    entries = yamlio.read(item.file)
    for e in entries:
        if str(e.get("id")) == iid:
            e["intent"] = [*(e.get("intent") or []), *recs]
    yamlio.write(item.file, entries)


def _add(spec: Spec, root: Path, op: Op) -> str:
    kind = op.kind
    _check_fields(kind, op.fields, f"add {kind}")
    if kind == "element":
        if not op.id:
            raise EditError("adding a system element needs an `id`, such as STORAGE")
        if op.id in spec.elements:
            raise EditError(f"system element {op.id} already exists")
        yamlio.write(root / "elements" / op.id / "element.yaml", {"id": op.id, **op.fields})
        return op.id
    if kind in ("need", "system", "constraint"):
        element = _root_id(spec)
        prefix = "NEED-" if kind == "need" else f"{element}-"
    elif kind == "decision":
        element = (op.fields.get("elements") or [None])[0]
        prefix = "DR-"
        if not element:
            raise EditError("a decision record needs `elements:`; the first one is where it's filed")
    else:
        element = op.element
        if not element:
            raise EditError(f"adding a {kind} needs `element:`, the system element it belongs to")
        prefix = f"{element}-V" if kind == "vi" else f"{element}-"
    if element not in spec.elements:
        raise EditError(f"unknown system element {element}")
    new_id = op.id or _next_id(spec, prefix)
    if new_id in spec.items:
        raise EditError(f"{new_id} already exists; omit `id` to have one allocated")
    if new_id in spec.retired_ids():
        raise EditError(f"{new_id} was retired and can't be reused; omit `id` to get a fresh one")
    entry = {"id": new_id}
    if kind in ("system", "constraint"):
        entry["kind"] = kind
    entry.update(op.fields)
    path = root / "elements" / element / KIND_FILES[kind]
    entries = yamlio.read(path) if path.exists() else []
    entries.append(entry)
    yamlio.write(path, entries)
    return new_id


def _modify(spec: Spec, op: Op) -> str:
    if op.id in spec.elements:
        element = spec.elements[op.id]
        _check_fields("element", list(op.fields) + list(op.unset), f"modify {op.id}")
        data = dict(element.data)
        data.update(op.fields)
        for k in op.unset:
            data.pop(k, None)
        yamlio.write(element.file, data)
        return op.id
    item = spec.items.get(op.id)
    if item is None:
        raise EditError(f"modify {op.id}: no such item" + _retired_hint(spec, op.id))
    _check_fields(item.kind, list(op.fields) + list(op.unset), f"modify {op.id}")
    entries = yamlio.read(item.file)
    for e in entries:
        if str(e.get("id")) == op.id:
            e.update(op.fields)
            for k in op.unset:
                e.pop(k, None)
    yamlio.write(item.file, entries)
    return op.id


def _remove(spec: Spec, root: Path, op: Op, change_id: str) -> str:
    item = spec.items.get(op.id)
    if item is None:
        raise EditError(f"remove {op.id}: no such item" + _retired_hint(spec, op.id))
    entries = [e for e in yamlio.read(item.file) if str(e.get("id")) != op.id]
    if entries:
        yamlio.write(item.file, entries)
    else:
        item.file.unlink()
    retired = yamlio.read(root / "retired.yaml") if (root / "retired.yaml").exists() else []
    retired.append({"element": item.element, "ids": [op.id], "note": f"{op.id}, in {change_id}: {op.reason}"})
    yamlio.write(root / "retired.yaml", retired)
    path = spec.locks_path()
    if path.exists():
        yamlio.write(path, [a for a in yamlio.read(path) or [] if a.get("id") != op.id])
    return op.id


def _retired_hint(spec: Spec, item_id: str) -> str:
    return " (it was retired; see retired.yaml)" if item_id in spec.retired_ids() else ""


# ---------------------------------------------------------------- impact (CLI-5, CLI-6)
def affected(spec: Spec, touched: list[str], adding: set[str], drafts: set[str] = frozenset(),
             approved: set[str] | None = None) -> dict[str, str]:
    """Approved or depended-on items an edit affects, each with the reason it's affected.

    `drafts` are items an agent added earlier in the open change and no person has locked since: they're the
    agent's own work, so editing them alters nothing a person gave."""
    out: dict[str, str] = {}
    if approved is None:
        approved = approved_ids(spec)
    raised = {t: review.engineer_marks(spec, t) for t in touched if t not in adding and t not in drafts}
    for t in touched:
        if t in adding:
            continue
        if t in approved:
            out[t] = "a person locked it; this edit changes what they locked"
        elif raised.get(t):  # SYS-37: the engineer will be asked about this alteration
            out[t] = f"{' and '.join(raised[t])}; the change record will ask whether to keep this alteration"
        for r in spec.of_kind("requirement"):
            if r.data.get("traces_to") == t:
                out.setdefault(r.id, f"refines {t}")
        for r in spec.of_kind("system", "constraint"):
            if t in (r.data.get("serves") or []):
                out.setdefault(r.id, f"serves {t}")
        for v in spec.of_kind("vi"):
            if t in (v.data.get("verifies") or []):
                out.setdefault(v.id, f"verifies {t}")
        for d in spec.of_kind("decision"):
            if re.search(rf"\b{re.escape(t)}\b", str(d.data.get("requirements", ""))):
                out.setdefault(d.id, f"records a decision about {t}")
        for e in spec.elements.values():
            if t in e.depends_on:
                out.setdefault(e.id, f"depends on {t}")
            if e.parent == t:
                out.setdefault(e.id, f"is part of {t}")
    for t in touched:  # items edited in the same batch are handled by their own reason
        if t not in approved and not raised.get(t):
            out.pop(t, None)
    return {k: v for k, v in out.items() if k not in touched or k in approved or raised.get(k)}


def approved_ids(spec: Spec) -> set[str]:
    return {s["id"] for s in check.approval_status(spec) if s["state"] == "approved"}


def _drafts(spec: Spec, change) -> set[str]:
    """Items the open change added that no person has locked since (see `affected`)."""
    added = {e.get("id") for e in change.data.get("entries") or [] if e.get("op") == "add"}
    return {i for i in added if not review.history(spec, i)}


def _only_gains_dependencies(before: Spec, after: Spec, iid: str) -> bool:
    """An element that only gains dependencies means nothing new to what's recorded about it, or to its dependents."""
    if iid not in before.elements or iid not in after.elements:
        return False
    b, a = before.elements[iid].data, after.elements[iid].data
    same = all(b.get(k) == a.get(k) for k in ("title", "purpose", "parent"))
    return same and set(b.get("depends_on") or []) <= set(a.get("depends_on") or [])


def _fingerprint(spec: Spec, item_id: str) -> str | None:
    """Only a change to an item's meaning affects what depends on it (DR-19)."""
    if item_id in spec.elements:
        return fingerprint.of_element(spec.elements[item_id])
    item = spec.items.get(item_id)
    return fingerprint.of_item(item) if item else None


def _data(spec: Spec, item_id: str) -> dict:
    """Every field of an item: logged in full, so changes to test links stay visible to auditors."""
    if item_id in spec.elements:
        data = spec.elements[item_id].data
    elif item_id in spec.items:
        data = spec.items[item_id].data
    else:
        return {}
    return {k: copy.deepcopy(v) for k, v in data.items() if k != "id" and v not in (None, "", [], {})}


def _diff(before: dict, after: dict) -> tuple[dict, dict]:
    keys = [k for k in dict.fromkeys(list(before) + list(after)) if before.get(k) != after.get(k)]
    return {k: before[k] for k in keys if k in before}, {k: after[k] for k in keys if k in after}


# ---------------------------------------------------------------- retrying a batch (CLI-17)
def _last_path(root: Path) -> Path:
    key = hashlib.sha1(str(root.resolve()).encode()).hexdigest()[:12]
    return Path(tempfile.gettempdir()) / "syseng" / key / "last-edit.yaml"


def save_last(root: Path, doc) -> None:
    """Keeps a batch that needs acknowledgments or fixes, so `spec edit --retry` can send it again."""
    yamlio.write(_last_path(root), doc)


def load_last(root: Path):
    path = _last_path(root)
    if not path.exists():
        raise EditError("there's no batch to retry: `--retry` reuses the last batch that needed acknowledgments "
                        "or had errors")
    return yamlio.read(path)


def clear_last(root: Path) -> None:
    _last_path(root).unlink(missing_ok=True)


def with_acks(doc, acks: list[str]):
    """Adds `ID=note` acknowledgments from the command line to a batch."""
    doc = {"edits": doc} if isinstance(doc, list) else dict(doc or {})
    merged = dict(doc.get("acks") or {})
    for ack in acks:
        iid, sep, note = ack.partition("=")
        if not sep or not iid.strip() or not note.strip():
            raise EditError(f"an acknowledgment looks like ID=note; got {ack!r}")
        merged[iid.strip()] = note.strip()
    doc["acks"] = merged
    return doc


def _brief(text: str, limit: int = 90) -> str:
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def _value_lines(prefix: str, value) -> list[str]:
    """A field's value, keeping the lines of multi-line text (CLI-19)."""
    if isinstance(value, str) and "\n" in value.strip():
        return [prefix] + [f"      {line}" if line.strip() else "" for line in value.strip().splitlines()]
    return [f"{prefix} {changes._one_line(value)}"]


def _context_lines(before: Spec, after: Spec, ops: list[Op], ids: list[str]) -> list[str]:
    lines = []
    for op, iid in zip(ops, ids):
        b, a = _diff(_data(before, iid), _data(after, iid))
        item = after.items.get(iid) or before.items.get(iid)
        where = f"{item.kind}, in {item.element}" if item else "system element"
        lines.append(f"{op.op} {iid} [{where}]")
        for key in dict.fromkeys(list(b) + list(a)):
            if key in b:
                lines += _value_lines(f"  - {key}:", b[key])
            if key in a:  # additions are echoed briefly; the change record keeps the full text
                lines += ([f"  + {key}: {_brief(changes._one_line(a[key]))}"] if op.op == "add"
                          else _value_lines(f"  + {key}:", a[key]))
        parent = (_data(after, iid) or _data(before, iid)).get("traces_to")
        if parent:
            lines.append(f"  refines {changes._label(after, parent)}")
        if op.op != "add":  # what an agent weighs before changing an item (CLI-13)
            lines.append(f"  attention: {review.describe(before, iid)}")
    return lines


# ---------------------------------------------------------------- conflicts (CLI-22, DR-57)
def _conflict_named(spec: Spec, change, ref: str) -> dict:
    """The decision an edit's `conflict:` names: `D2` in the open change, or `<change> D2` in another."""
    parts = ref.split()
    wanted = parts[-1]
    pool = [change] if len(parts) == 1 else [c for c in changes.all_changes(spec) if c.id == parts[0]]
    for c in pool:
        for d in c.data.get("decisions") or []:
            if d.get("id") == wanted:
                return d
    raise EditError(f"conflict {ref!r} names no decision; raise it first with `spec decide` (kind: conflict)")


def _guard_intent(spec: Spec, change, ops: list[Op], ids: list[str], meaningful: list[str]) -> None:
    """In spec-first mode, a change of meaning to an item a person locked or stated waits for that person (CLI-22)."""
    refused = []
    for op, iid in zip(ops, ids):
        if iid not in meaningful or op.op == "add":
            continue
        if levels.level_of(spec, iid).level not in (levels.EXPLICIT, levels.STATED):
            continue
        if op.rewording or op.requested:
            continue
        if op.conflict:
            d = _conflict_named(spec, change, op.conflict)
            if d.get("status") == "resolved" and iid in (d.get("involves") or []):
                continue
        refused.append(iid)
    if refused:
        raise EditError(
            f"{', '.join(changes._label(spec, i) for i in refused)}: a person locked or stated "
            f"{'these' if len(refused) > 1 else 'this'}, and this is a spec-first change, so changing the meaning "
            "waits for them. Raise the conflict with `spec decide` (kind: conflict, involves: the items, options "
            "with the new text each would give), and once they've chosen, send the edit again with `conflict: D<n>`. "
            "If the meaning doesn't change, mark the edit `rewording: true`; if the person asked for this very "
            "change, add their request as `intent:` with basis stated.")


# ---------------------------------------------------------------- entry point
def run(root: Path, doc, dry_run: bool = False) -> Result:
    ops, acks = parse(doc)
    spec = model.load(root)
    change = changes.current(spec)
    if change is None:
        raise EditError("no change is open. Start one with `spec change start \"<what the engineer asked for>\"`; "
                        "every edit is logged in it with its reason.")
    result = Result()
    person = people.person(spec.repo_root())[0]
    now = datetime.datetime.now().astimezone().isoformat(timespec="minutes")
    stamp = now.replace("T", " ")[:16]
    for op in ops:
        if op.conflict:
            _conflict_named(spec, change, op.conflict)
    with tempfile.TemporaryDirectory() as tmp:
        scratch = Path(tmp) / "spec"
        shutil.copytree(root, scratch)
        ids = apply_ops(scratch, ops, change.id, person, stamp)
        after = model.load(scratch)
        after.repo = spec.repo_root()  # test links resolve in the real repository (CHECK-4)
        result.ids = ids
        result.context = _context_lines(spec, after, ops, ids)
        adding = {i for op, i in zip(ops, ids) if op.op == "add"}
        meaningful = [i for op, i in zip(ops, ids) if op.op == "remove" or (
            op.op == "modify" and _fingerprint(spec, i) != _fingerprint(after, i)
            and not _only_gains_dependencies(spec, after, i))]
        if change.data.get("mode") == "spec-first":
            _guard_intent(spec, change, ops, ids, meaningful)
        drafts = _drafts(spec, change)
        approved = approved_ids(spec)
        needed = affected(spec, meaningful, adding, drafts, approved)
        missing = {k: v for k, v in needed.items() if k not in acks}
        if missing:
            result.needs_acks = missing
            return result
        render.write_views(after)
        old_errors = {(f.code, f.item, f.message) for f in check.check(spec) if f.severity == "error"}
        new = [f for f in check.check(after)  # a conflict is raised once the change is done, not per edit (C001)
               if f.severity == "error" and f.code not in ("R001", "C001", "F001")
               and (f.code, f.item, f.message) not in old_errors]
        if new:
            for f in new:  # point at the real files, not the scratch copy
                if f.file is not None and f.file.is_relative_to(scratch):
                    f.file = root / f.file.relative_to(scratch)
            result.errors = new
            return result
    if dry_run:
        return result
    apply_ops(root, ops, change.id, person, stamp)
    after = model.load(root)
    for op, iid in zip(ops, ids):
        entry = {"op": op.op, "id": iid, "at": now, "reason": op.reason}  # CHANGE-16
        marks = review.engineer_marks(spec, iid) if iid in meaningful and iid not in drafts else []
        if marks:  # CHANGE-14: listed in the change record until the engineer answers
            entry["raised"] = marks
            entry["level"] = levels.level_of(spec, iid).level  # the level the item had when it was altered
            entry["fingerprint_before"] = _fingerprint(spec, iid)
            entry["fingerprint_after"] = _fingerprint(after, iid)
        for key, value in (("rewording", op.rewording), ("conflict", op.conflict), ("requested", op.requested)):
            if value:  # how an alteration answers for itself (CHECK-26), and what the diff calls it (DIFF-3)
                entry[key] = value
        b, a = _diff(_data(spec, iid), _data(after, iid))
        if b:
            entry["before"] = b
        if a:
            entry["after"] = a
        own = {k: v for k, v in acks.items()
               if iid in meaningful and k in affected(spec, [iid], adding, drafts, approved)}
        if own:
            entry["acks"] = own
        change.data.setdefault("entries", []).append(entry)
    change.save()
    render.write_views(model.load(root))
    result.applied = True
    return result
