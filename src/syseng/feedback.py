"""Applying a person's feedback from the review page (SYS-46, SYS-51, SYS-52, CLI-23, CLI-27; DR-60, DR-62).

The block names its person and carries the fingerprint of each item and decision it acts on. The CLI
applies it mechanically, in that person's name, and never interprets it:

  - locks, unlocks and decision choices are recorded only where the item or decision still matches
    what the page showed; each stale one is refused and reported;
  - keeping an alteration re-records the item at its earlier level (a lock, or a fresh intent record);
  - removing an intent record is an edit, logged with the person as the reason;
  - everything that needs judgment (comments, corrections, roll-backs, general notes) becomes a
    feedback item in the open change, which the agent answers with `spec feedback respond`;
  - the review itself is recorded, so the next comparison starts from it (MODEL-39).

It works wherever the block came from: pasted into the conversation, or copied from a pull request.
"""

import datetime
import re
from dataclasses import dataclass, field
from pathlib import Path

from syseng import changes, edit, fingerprint, levels, model, pagedata, records, review, yamlio
from syseng.model import Spec

FENCE = re.compile(r"```syseng-feedback\s*\n(.*?)```", re.S)


class FeedbackError(Exception):
    pass


@dataclass
class Report:
    locked: list[str] = field(default_factory=list)
    already: list[str] = field(default_factory=list)  # sent again, already on record: nothing to do
    unlocked: list[str] = field(default_factory=list)
    kept: list[str] = field(default_factory=list)
    resolved: list[str] = field(default_factory=list)
    removed_intent: list[str] = field(default_factory=list)
    to_answer: list[str] = field(default_factory=list)
    refused: list[str] = field(default_factory=list)


def parse(text: str) -> records.FeedbackBlock:
    m = FENCE.search(text)
    body = m.group(1) if m else text
    try:
        data = yamlio.loads(body)
    except Exception as e:  # noqa: BLE001 - any YAML problem is reported the same way
        raise FeedbackError(f"can't read the feedback block: {e}") from e
    wrong = records.problems(records.FeedbackBlock, data)
    if wrong:
        raise FeedbackError("the feedback block isn't valid: " + "; ".join(wrong))
    return records.FeedbackBlock.model_validate(data)


def _now() -> str:
    return datetime.datetime.now().astimezone().isoformat(timespec="minutes")


def apply(spec: Spec, block: records.FeedbackBlock) -> Report:
    report = Report()
    if block.repository and block.repository != spec.repo_root().name:
        report.refused.append(f"the block is for {block.repository}, not {spec.repo_root().name}; applied anyway, "
                              "since IDs and fingerprints decide what matches")
    change = changes.current(spec)
    if change is None:
        change = changes.start(spec, f"Apply {block.by}'s review {block.review} from the review page", None, None,
                               "review-feedback")
        spec = model.load(spec.root)
    person = block.by
    now = _now()
    locks_to_add, items_feedback = [], []
    lockers = [i for i in block.items if i.lock is True]
    for fb in block.items:
        kd = review.kind_and_data(spec, fb.id)
        if kd is None:
            report.refused.append(f"{fb.id}: no longer in the spec")
            continue
        current = fingerprint.of(*kd)
        fresh = fb.fingerprint == current
        acted = fb.lock is not None or fb.alteration or fb.intent
        if acted and not fresh:
            report.refused.append(f"{fb.id}: changed since the page showed it, so its lock, answer or intent fix "
                                  f"wasn't applied; regenerate the page and ask again")
        if fresh and fb.lock is True and levels.level_of(spec, fb.id).level == levels.EXPLICIT:
            report.already.append(f"{fb.id} locked")
        elif fresh and fb.lock is not None:
            locks_to_add.append({"id": fb.id, "fingerprint": current, "locked_at": now, "by": person, "via": "page",
                                 "batch": len(lockers) if fb.lock else None, "review": block.review,
                                 "text": fingerprint.summary(*kd), **({} if fb.lock else {"released": True})})
            (report.locked if fb.lock else report.unlocked).append(fb.id)
        if fresh and fb.alteration == "keep" and levels.kept(spec, fb.id):
            report.already.append(f"{fb.id} kept")
        elif fresh and fb.alteration == "keep":
            report.kept.append(fb.id)
            _keep(spec, fb.id, person, now, block.review, locks_to_add, kd)
        if fb.alteration == "roll back":
            items_feedback.append({"id": fb.id, "kind": "roll back",
                                   "comment": f"{person} asked for this alteration to be rolled back."})
        for fix in fb.intent:
            if not fresh:
                continue
            if fix.action == "remove":
                if _remove_intent(spec, fb.id, fix, person, block.review):
                    report.removed_intent.append(fb.id)
                    spec = model.load(spec.root)
                else:
                    report.refused.append(f"{fb.id}: intent record {fix.record + 1} isn't the one the page showed")
            else:
                items_feedback.append({"id": fb.id, "kind": "correction", "record": fix.record,
                                       "comment": fix.correction or "(no text given)"})
        if fb.wording:  # the agent applies it as the person's stated intent (DR-66)
            items_feedback.append({"id": fb.id, "kind": "wording", "comment": fb.wording,
                                   **({} if fresh else {"note": "the item changed since the page showed it"})})
        if fb.comment:
            items_feedback.append({"id": fb.id, "kind": "comment", "comment": fb.comment,
                                   **({} if fresh else {"note": "the item changed since the page showed it"})})
    for d in block.decisions:
        target = next((c for c in changes.all_changes(spec) if c.id == d.change), None)
        found = next((x for x in (target.data.get("decisions") or []) if x.get("id") == d.id), None) if target else None
        if found is None:
            report.refused.append(f"{d.change} {d.id}: no such decision")
            continue
        if d.choose:
            if found.get("status") != "open":
                report.refused.append(f"{d.id}: already resolved ({found.get('chosen')})")
            elif pagedata.decision_fingerprint(found) != d.fingerprint:
                report.refused.append(f"{d.id}: its options changed since the page showed them")
            elif not 1 <= d.choose <= len(found.get("options") or []):
                report.refused.append(f"{d.id}: there's no option {d.choose}")
            else:
                option = found["options"][d.choose - 1]
                label = option.get("label", "")
                changes.resolve(target, [d.id], f"{person} chose {label} on the review page (summary)", d.choose,
                                by=person)
                report.resolved.append(f"{d.id} → {label}")
                spec = model.load(spec.root)
                for iid in option.get("keeps") or []:  # keeping re-records each item at its earlier level (DR-54)
                    kd = review.kind_and_data(spec, iid)
                    if kd is not None:
                        _keep(spec, iid, person, now, block.review, locks_to_add, kd, note=f"kept under {d.id}")
                        report.kept.append(iid)
                for iid in option.get("rolls_back") or []:
                    items_feedback.append({"id": iid, "kind": "roll back",
                                           "comment": f"{person} chose {label} for {d.id}, which rolls this back."})
        if d.comment:
            items_feedback.append({"decision": f"{d.change} {d.id}", "kind": "comment", "comment": d.comment})
    if locks_to_add:
        path = spec.locks_path()
        existing = (yamlio.read(path) or []) if path.exists() else []
        clean = [{k: v for k, v in r.items() if v is not None} for r in locks_to_add]
        yamlio.write(path, sorted(existing + clean, key=lambda a: (str(a.get("id")), levels.when(a))))
    if block.general:
        items_feedback.append({"kind": "general", "comment": block.general})
    said = {(f.get("by"), f.get("id"), f.get("decision"), f.get("kind"), f.get("comment"))
            for c in changes.all_changes(model.load(spec.root)) for f in c.data.get("feedback") or []}
    fresh_feedback = []
    for f in items_feedback:  # a comment sent again isn't asked twice
        if (person, f.get("id"), f.get("decision"), f.get("kind"), f.get("comment")) in said:
            report.already.append(f"{f.get('id') or f.get('decision') or 'general'} {f.get('kind')}")
        else:
            fresh_feedback.append(f)
    items_feedback = fresh_feedback
    change = changes.current(model.load(spec.root))
    entries = change.data.setdefault("feedback", [])
    for f in items_feedback:
        fid = f"F{len(entries) + 1}"
        entries.append({"n": fid, "by": person, "at": now, "review": block.review, **f, "response": None})
        report.to_answer.append(fid + (f" ({f['id']})" if f.get("id") else ""))
    change.save()
    _record_review(spec, block, now, report)
    return report


def _keep(spec: Spec, iid: str, person: str, now: str, review_id: str, locks: list, kd,
          note: str = "kept an alteration") -> None:
    """Keeping an alteration re-records the item at its earlier level (DR-54): a lock if it was locked, else intent."""
    if review.history(spec, iid):
        if not any(x["id"] == iid for x in locks):
            locks.append({"id": iid, "fingerprint": fingerprint.of(*kd), "locked_at": now, "by": person, "via": "page",
                          "review": review_id, "text": fingerprint.summary(*kd), "note": note})
        return
    basis = levels.level_of(spec, iid).level
    basis = basis if basis in levels.INTENT_BASES else "guided"
    edit.run(spec.root, {"edits": [{"modify": iid, "reason": f"{person} kept this alteration on the review page",
                                    "intent": {"basis": basis, "by": person, "when": now.replace("T", " ")[:16],
                                               "context": f"Reviewing an alteration on the review page (review {review_id}).",
                                               "said": "Kept the item as it now reads."}}]})


def _remove_intent(spec: Spec, iid: str, fix: records.IntentFix, person: str, review_id: str) -> bool:
    kd = review.kind_and_data(spec, iid)
    recs = levels.intent_records(kd[1])
    if not 0 <= fix.record < len(recs):
        return False
    rec = recs[fix.record]
    if (fix.when and str(rec.get("when")) != fix.when) or (fix.by and rec.get("by") != fix.by):
        return False
    remaining = [r for n, r in enumerate(recs) if n != fix.record]
    op = {"modify": iid, "reason": f"{person} said on the review page that this intent record isn't what they meant "
                                   f"(review {review_id})"}
    if remaining:
        op["set"] = {"intent": remaining}
    else:
        op["unset"] = ["intent"]
        if kd[0] in ("requirement", "system", "constraint", "decision") and not kd[1].get("basis"):
            op["set"] = {"basis": "derived"}  # with no intent left, an agent's item says where it came from
    result = edit.run(spec.root, {"edits": [op]})
    if result.needs_acks:
        result = edit.run(spec.root, {"edits": [op], "acks": {k: "the person removed the intent record"
                                                              for k in result.needs_acks}})
    return result.applied


def _record_review(spec: Spec, block: records.FeedbackBlock, now: str, report: Report) -> None:
    """MODEL-39: who reviewed, when, and on which version, and MODEL-43: what they did. A page made from uncommitted
    work also keeps the fingerprints of what it showed, from the local snapshot when there is one."""
    path = spec.root / "reviews.yaml"
    reviews = (yamlio.read(path) or []) if path.exists() else []
    entry = {"review": block.review, "by": block.by, "at": now, "generated": block.generated,
             "revision": block.revision, "dirty": block.dirty}
    did = {"locked": report.locked, "unlocked": report.unlocked, "kept": report.kept, "decided": report.resolved}
    entry["did"] = {k: list(v) for k, v in did.items() if v}
    if block.dirty:
        snap = spec.root.parent / ".syseng" / "reviews" / f"{block.review}.json"
        if snap.exists():
            import json
            data = json.loads(snap.read_text())
            entry["fingerprints"] = {i: it.get("fingerprint") for i, it in data.get("items", {}).items()}
        else:
            entry["fingerprints"] = {i.id: i.fingerprint for i in block.items}
    reviews.append(entry)
    yamlio.write(path, reviews)


def respond(spec: Spec, fid: str, response: str) -> dict:
    """The agent's answer to one feedback item (CHANGE-19); the person's next page shows it (SYS-52)."""
    for c in changes.all_changes(spec):
        for f in c.data.get("feedback") or []:
            if f.get("n") == fid and (c.is_open or f.get("response") is None):
                f["response"] = response
                f["responded"] = _now()
                c.save()
                return f
    raise FeedbackError(f"no feedback item {fid} waiting for a response")


def unanswered(spec: Spec) -> list[tuple[str, dict]]:
    c = changes.current(spec)
    return [(c.id, f) for f in (c.data.get("feedback") or []) if not f.get("response")] if c else []
