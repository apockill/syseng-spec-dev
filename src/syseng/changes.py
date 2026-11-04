"""Change records (CHANGE): what was asked, in which mode, what changed in the spec and why,
and the open decisions waiting for the engineer.

A change record is spec/changes/<date>-round-<N>[-<slug>].yaml. `spec change show --full` prints
it as text. At most one change is open at a time; `spec edit` logs every edit into it with its
reason (CHANGE-5).
"""

import datetime
import re
from dataclasses import dataclass
from pathlib import Path

from syseng import review, vcs, yamlio
from syseng.model import Spec

MODES = ("code-first", "spec-first")


@dataclass
class Change:
    path: Path
    data: dict

    @property
    def id(self) -> str:
        return self.path.stem

    @property
    def is_open(self) -> bool:
        return self.data.get("status") == "open"

    def save(self) -> None:
        yamlio.write(self.path, self.data)


def changes_dir(spec: Spec) -> Path:
    return spec.root / "changes"


def all_changes(spec: Spec) -> list[Change]:
    out = []
    for path in sorted(changes_dir(spec).glob("*.yaml"), key=lambda p: round_of(p.name)):
        data = yamlio.read(path) or {}
        out.append(Change(path, data))
    return out


def round_of(name: str) -> int:
    m = re.search(r"round-(\d+)", name)
    return int(m.group(1)) if m else 0


def current(spec: Spec) -> Change | None:
    open_changes = [c for c in all_changes(spec) if c.is_open]
    if len(open_changes) > 1:
        raise ChangeError("more than one change is open: " + ", ".join(c.id for c in open_changes)
                          + ". Close all but one with `spec change close --id <id>`.")
    return open_changes[0] if open_changes else None


class ChangeError(Exception):
    pass


def start(spec: Spec, request: str, mode: str | None, target: str | None, slug: str | None) -> Change:
    if current(spec):
        raise ChangeError(f"change {current(spec).id} is still open. Close it first with `spec change close`.")
    mode = mode or "code-first"  # CHANGE-9: a request that names no mode is code-first
    if mode not in MODES:
        raise ChangeError(f"mode must be one of {', '.join(MODES)}")
    impls = spec.config.get("implementations") or []
    names = [i.get("name") for i in impls]
    primary = next((i.get("name") for i in impls if i.get("primary")), names[0] if names else None)
    target = target or primary  # CHANGE-8: defaults to the primary implementation
    if names and target not in names:
        raise ChangeError(f"unknown implementation {target!r}; known: {', '.join(names)}")
    paths = list(changes_dir(spec).glob("*"))
    n = max([round_of(p.name) for p in paths] + [0]) + 1
    today = datetime.date.today().isoformat()
    name = f"{today}-round-{n}" + (f"-{_slug(slug)}" if slug else "")
    repo = spec.repo_root()
    try:  # CHANGE-23: where the change started, so a page on the trunk can compare against it (REVIEW-52)
        started_from = vcs.backend(repo).revision(repo)
    except vcs.VersionControlError:
        started_from = ""
    change = Change(changes_dir(spec) / f"{name}.yaml", {
        "request": request, "mode": mode, "target": target, "status": "open", "opened": today,
        **({"started_from": started_from} if started_from else {}), "entries": [], "decisions": []})
    change.save()
    return change


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:40]


def close(change: Change) -> None:
    change.data["status"] = "closed"
    change.data["closed"] = datetime.date.today().isoformat()
    change.save()


def add_decision(change: Change, decision: dict, replace: str | None = None) -> str:
    """Adds an open decision (CHANGE-3). It must offer options, one of them recommended (CHANGE-10)."""
    options = decision.get("options") or []
    if not decision.get("question"):
        raise ChangeError("a decision needs a `question`")
    if len(options) < 2:
        raise ChangeError("a decision needs at least two `options`")
    if sum(1 for o in options if o.get("recommended")) != 1:
        raise ChangeError("mark exactly one option `recommended: true`")
    if not decision.get("importance"):
        raise ChangeError("say why this decision ranks where it does, in `importance`")
    kind = decision.get("kind")
    if kind not in (None, "conflict"):
        raise ChangeError("`kind` is `conflict` for a conflict with what a person locked or stated, or left out")
    if kind == "conflict" and not decision.get("involves"):
        raise ChangeError("a conflict names the items it involves, in `involves`")
    for o in options:  # what choosing the option does to each item, so it can be applied as chosen (DR-57)
        for key in ("keeps", "rolls_back"):
            stray = [i for i in o.get(key) or [] if i not in (decision.get("involves") or [])]
            if stray:
                raise ChangeError(f"option {o.get('label')!r} {key.replace('_', ' ')} {', '.join(stray)}, which the "
                                  "decision doesn't involve")
    decisions = change.data.setdefault("decisions", [])
    if replace:  # CHANGE-20: an open decision is rewritten in place until the person answers it
        old = next((d for d in decisions if d.get("id") == replace), None)
        if old is None:
            raise ChangeError(f"{change.id} has no decision {replace}")
        if old.get("status") != "open":
            raise ChangeError(f"{replace} is already {old.get('status')}; file a new decision instead")
        did = replace
    else:
        did = f"D{len(decisions) + 1}"
    entry = {"id": did, **({"kind": kind} if kind else {}), "question": decision["question"],
             "importance": decision["importance"], "involves": decision.get("involves") or [], "options": options,
             **({"replaces": decision["replaces"]} if decision.get("replaces") else {}), "status": "open"}
    if replace:
        decisions[decisions.index(old)] = entry
    else:
        decisions.append(entry)
    change.save()
    return did


def _stamp() -> str:
    return datetime.datetime.now().astimezone().isoformat(timespec="minutes")


def qualified(change: Change, did: str) -> str:
    """A decision's reference that holds across changes, whose numbers each start at D1 (CHANGE-26)."""
    return f"{change.id}/{did}"


def find_decision(spec: Spec, ref: str, default: Change | None) -> tuple[Change, dict]:
    """The decision a reference names (CHANGE-26): `<change>/D2` (or `<change> D2`) in that change, where `<change>`
    is its ID or a part of it naming no other, such as round-63; a bare `D2` in `default`, the open change, unless
    another change also has an open D2, when the reference must say which."""
    ref = ref.strip()
    m = re.fullmatch(r"(?:(.+?)[/ ])?(D\d+)", ref)
    if not m:
        raise ChangeError(f"{ref!r} isn't a decision; name one as D<n> in the open change, or <change>/D<n>")
    where, did = m.group(1), m.group(2)
    every = all_changes(spec)
    if where:
        exact = [c for c in every if c.id == where]
        pool = exact or [c for c in every if re.search(rf"(^|-){re.escape(where)}($|-)", c.id)]
        if not pool:
            raise ChangeError(f"no change record is called {where!r}")
        if len(pool) > 1:
            raise ChangeError(f"{where!r} names more than one change: {', '.join(c.id for c in pool)}; use the full ID")
        change = pool[0]
    else:
        change = default
        others = [qualified(c, did) for c in every if default is None or c.path != default.path
                  if any(x.get("id") == did and x.get("status") == "open" for x in c.data.get("decisions") or [])]
        here = change is not None and any(x.get("id") == did for x in change.data.get("decisions") or [])
        if others:  # another change has an open decision of that number: a bare reference could mean either
            raise ChangeError(f"{did} could mean {' or '.join(([qualified(change, did)] if here else []) + others)}; "
                              "name the one you mean as <change>/D<n>")
        if not here:
            raise ChangeError(f"{change.id if change else 'the open change'} has no decision {did}")
    d = next((x for x in change.data.get("decisions") or [] if x.get("id") == did), None)
    if d is None:
        raise ChangeError(f"{change.id} has no decision {did}")
    return change, d


def withdraw(change: Change, did: str, reason: str, into: Change | None = None) -> None:
    """CHANGE-21: an open decision the conversation has overtaken is withdrawn with a reason, not left to linger.
    One of an earlier change is withdrawn from the open change, `into`, which logs the act (CHANGE-24); the earlier
    record keeps what was asked, and gains only its new status and why."""
    if not (reason or "").strip():
        raise ChangeError("say why the decision is withdrawn")
    d = next((x for x in change.data.get("decisions") or [] if x.get("id") == did), None)
    if d is None:
        raise ChangeError(f"{change.id} has no decision {did}")
    if d.get("status") != "open":
        raise ChangeError(f"{did} is already {d.get('status')}")
    now = _stamp()
    elsewhere = into is not None and into.path != change.path
    d.update({"status": "withdrawn", "withdrawn_because": reason, "withdrawn": now,
              **({"withdrawn_in": into.id} if elsewhere else {})})
    change.save()
    if elsewhere:
        into.data.setdefault("withdrawals", []).append(
            {"decision": qualified(change, did), "because": reason, "at": now})
        into.save()


def replace_earlier(current: Change, earlier: Change, did: str, decision: dict) -> str:
    """CHANGE-25: an open decision of an earlier change is replaced by a new one in the open change, and withdrawn
    there, so the earlier record keeps what it asked."""
    old = next((x for x in earlier.data.get("decisions") or [] if x.get("id") == did), None)
    if old is None or old.get("status") != "open":
        raise ChangeError(f"{qualified(earlier, did)} is {'already ' + str(old.get('status')) if old else 'not there'}; "
                          "file a new decision instead")
    new = add_decision(current, {**decision, "replaces": qualified(earlier, did)})
    withdraw(earlier, did, f"replaced by {qualified(current, new)}", into=current)
    return new


def resolve(change: Change, ids: list[str], words: str, option: int | None, by: str | None = None) -> list[str]:
    """Records the engineer's choice. With no option, takes the recommended one (CHANGE-12). A withdrawn decision
    stays withdrawn (CHANGE-27): only an open or answered one takes a choice."""
    by_id = {d["id"]: d for d in change.data.get("decisions") or []}
    unknown = [i for i in ids if i not in by_id]
    if unknown:
        raise ChangeError(f"unknown decisions: {', '.join(unknown)}")
    gone = [f"{i} ({by_id[i].get('withdrawn_because', '')})" for i in ids if by_id[i].get("status") == "withdrawn"]
    if gone:
        raise ChangeError(f"withdrawn, so there's nothing to choose: {'; '.join(gone)}")
    done = []
    for i in ids:
        d = by_id[i]
        opts = d.get("options") or []
        chosen = (opts[option - 1] if option else next(o for o in opts if o.get("recommended")))
        d.update({"status": "resolved", "chosen": chosen.get("label"), "words": words,
                  "resolved": datetime.date.today().isoformat(), **({"by": by} if by else {})})
        done.append(i)
    change.save()
    return done


def add_proposal(change: Change, ids: list[str], why: str) -> None:
    """SYS-38: an agent proposes items for the engineer to lock, saying why they deserve it."""
    if not (why or "").strip():
        raise ChangeError("say why these items deserve the engineer's attention")
    change.data.setdefault("proposals", []).append({"ids": ids, "why": why, "proposed": _stamp()})
    change.save()


def withdrawn_from(proposal: dict) -> set[str]:
    """The items an agent took back out of a proposal (CHANGE-28)."""
    return {str(w.get("id")) for w in proposal.get("withdrawn") or []}


def pending_proposals(spec: Spec, iid: str) -> list[tuple[Change, dict]]:
    return [(c, p) for c in all_changes(spec) for p in c.data.get("proposals") or []
            if iid in (p.get("ids") or []) and iid not in withdrawn_from(p)]


def withdraw_proposals(spec: Spec, current: Change, ids: list[str], reason: str) -> list[str]:
    """CHANGE-28: an agent takes back its proposal that the engineer lock items, with a reason, in whichever change
    proposed them. The proposal keeps its items and reason; it gains the withdrawal, logged in the open change."""
    if not (reason or "").strip():
        raise ChangeError("say why the proposal is withdrawn")
    missing = [i for i in ids if not pending_proposals(spec, i)]
    if missing:
        raise ChangeError(f"no proposal to lock {', '.join(missing)} is waiting; nothing withdrawn")
    now = _stamp()
    for iid in ids:
        for c, p in pending_proposals(spec, iid):
            target = current if c.path == current.path else c
            prop = next(x for x in target.data["proposals"] if x == p)
            prop.setdefault("withdrawn", []).append(
                {"id": iid, "because": reason, "at": now, **({} if target is current else {"withdrawn_in": current.id})})
            target.save()
    current.data.setdefault("withdrawals", []).append({"proposal": ids, "because": reason, "at": now})
    current.save()
    return ids


# ---------------------------------------------------------------- view
def _label(spec: Spec, item_id: str) -> str:
    """An ID with a short title, so nobody has to look it up (AGENT-44)."""
    item = spec.items.get(item_id)
    if item is None:
        element = spec.elements.get(item_id)
        return f"{item_id} ({element.title}, a system element)" if element and element.title else item_id
    text = str(item.data.get("title") or item.data.get("text") or item.data.get("description") or "")
    words = text.split()
    short = " ".join(words[:9]) + ("…" if len(words) > 9 else "")
    return f"{item_id} ({short})" if short else item_id


def _why_careful(spec: Spec, item_id: str) -> list[str]:
    """Why an item deserves a careful read (CHANGE-11): your own words, or decisions behind it."""
    item = spec.items.get(item_id)
    if item is None:
        return []
    reasons = []
    if item.data.get("origin") == "engineer" or item.data.get("decided_by") == "engineer":
        reasons.append("your words")
    reasons += [d.id for d in spec.of_kind("decision")
                if re.search(rf"\b{re.escape(item_id)}\b", str(d.data.get("requirements", "")))]
    return reasons


def view(spec: Spec, change: Change) -> str:
    d = change.data
    out = [f"# Change record: {change.id}", "",
           "*Generated by `spec` from the YAML file beside it. Don't edit this file by hand.*", "",
           f"*{d.get('opened', '')} · {d.get('mode', '')} · target: {d.get('target', '')} · "
           f"{'open' if change.is_open else 'closed ' + str(d.get('closed', ''))}*", "",
           f"**Request (summarized):** {d.get('request', '')}", ""]
    decisions = d.get("decisions") or []
    open_ds = [x for x in decisions if x.get("status") == "open"]
    out += ["## Open decisions, most consequential first", ""]
    if not open_ds:
        out += ["None.", ""]
    for x in open_ds:
        out.append(f"- **{x['id']}: {x.get('question', '')}**")
        out.append(f"  - *Why it ranks here:* {x.get('importance', '')}")
        involved = x.get("involves") or []
        if involved:
            out.append(f"  - *Involves:* {', '.join(_label(spec, i) for i in involved)}")
            careful = [f"{i} ({', '.join(_why_careful(spec, i))})" for i in involved if _why_careful(spec, i)]
            if careful:  # CHANGE-11: don't skim these
                out.append(f"  - ⚠ *Read before accepting; these carry your words or recorded decisions:* "
                           f"{'; '.join(careful)}")
        for n, o in enumerate(x.get("options") or [], 1):
            rec = " **(recommended)**" if o.get("recommended") else ""
            detail = f": {o['detail']}" if o.get("detail") else ""
            out.append(f"  {n}. {o.get('label', '')}{rec}{detail}")
    if open_ds:
        refs = [x["id"] if change.is_open else qualified(change, x["id"]) for x in open_ds]
        out += ["", f"To accept every recommendation: `spec resolve {' '.join(refs)} "
                    f"--words \"<your words>\"`.", ""]
    out += _alterations_section(spec, change) + _proposals_section(spec, change)
    resolved = [x for x in decisions if x.get("status") == "resolved"]
    if resolved:
        out += ["## Resolved decisions", ""]
        out += [f"- **{x['id']}:** {x.get('question', '')} → {x.get('chosen', '')} ({x.get('words', '')})"
                for x in resolved]
        out.append("")
    withdrawn = [x for x in decisions if x.get("status") == "withdrawn"]
    if withdrawn:
        out += ["## Withdrawn decisions", ""]
        out += [f"- **{x['id']}:** {x.get('question', '')} (withdrawn"
                + (f" in {x['withdrawn_in']}" if x.get("withdrawn_in") else "") + f": {x.get('withdrawn_because', '')})"
                for x in withdrawn]
        out.append("")
    acts = d.get("withdrawals") or []
    if acts:  # CHANGE-24: what this change withdrew from earlier ones
        out += ["## Withdrawn here", ""]
        out += [f"- {'decision ' + a['decision'] if a.get('decision') else 'proposal to lock ' + ', '.join(a.get('proposal') or [])}: "
                f"{a.get('because', '')}" for a in acts]
        out.append("")
    entries = d.get("entries") or []
    out += ["## Changes to the spec", ""]
    if not entries:
        out += ["None yet.", ""]
    for e in entries:
        out.append(f"- **{e.get('op', '')} {_label(spec, e.get('id', ''))}**: {e.get('reason', '')}")
        before, after = e.get("before") or {}, e.get("after") or {}
        for key in dict.fromkeys(list(before) + list(after)):
            if before.get(key) != after.get(key):
                if key in after and _is_block(after[key]):  # keep the structure of multi-line text
                    if key in before:
                        out.append(f"  - {key}, before: ~~{_one_line(before[key])}~~")
                    out.append(f"  - {key}{', now' if key in before else ''}:")
                    out += ["    " + line if line.strip() else "" for line in str(after[key]).strip().splitlines()]
                elif key in before and key in after:
                    out.append(f"  - {key}: ~~{_one_line(before[key])}~~ → {_one_line(after[key])}")
                elif key in after:
                    out.append(f"  - {key}: {_one_line(after[key])}")
                else:
                    out.append(f"  - {key} removed: ~~{_one_line(before[key])}~~")
        for ack_id, note in (e.get("acks") or {}).items():
            out.append(f"  - *Acknowledged {_label(spec, ack_id)}:* {note}")
    friction = d.get("friction") or []
    if friction:
        out += ["", "## Agent friction", ""]
        out += [f"- **Worked around:** {f.get('workaround', '')} **Proposal:** {f.get('proposal', '')}"
                for f in friction]
    return "\n".join(out).rstrip("\n") + "\n"


def _is_block(value) -> bool:
    return isinstance(value, str) and "\n" in value.strip()


_MENTION = re.compile(r"\b(?:[A-Z]+-V?\d+)\b")
_CONTEXT_FIELDS = {  # what the engineer needs to judge an item without looking anything up (REVIEW-18)
    "decision": [("context", "Context"), ("decision", "Decision"), ("alternatives", "Alternatives"),
                 ("consequences", "Consequences")],
    "vi": [("description", "Checks"), ("verifies", "Verifies")],
}
_REQUIREMENT_FIELDS = [("why", "Why"), ("refines", "Refines"), ("source", "Source"), ("context", "Context")]


def _full(spec: Spec, iid: str) -> tuple[str, list[str]]:
    """An item's heading and full context, with a line naming every other item it mentions (REVIEW-18, REVIEW-19)."""
    if iid in spec.elements:
        e = spec.elements[iid]
        body = [f"- *System element:* {e.data.get('purpose', '')}", f"- *Part of:* {_label(spec, e.parent) if e.parent else 'nothing (it is the root)'}"]
        return f"{iid}: {e.title}", body + _mentions(spec, iid, body)
    item = spec.items.get(iid)
    if item is None:
        return iid, []
    d = item.data
    if item.kind == "decision":
        head = f"{iid}: {d.get('title', '')}"
        decided = [r for r in review.parents(spec, iid) if r in spec.items]
        body = [_block("- *Decides:*", "")] if decided else []
        body += [_block(f"  - {r}:", spec.items[r].data.get("text", "")) for r in decided]
    else:
        head = iid
        body = [_block(">", d.get("text") or d.get("description") or "")]
        ups = review.parents(spec, iid)
        if ups and item.kind != "vi":
            body.append(f"- *Under:* {', '.join(_label(spec, u) for u in ups)}")
    for key, label in _CONTEXT_FIELDS.get(item.kind, _REQUIREMENT_FIELDS):
        value = d.get(key)
        if value:
            shown = ", ".join(_label(spec, v) for v in value) if isinstance(value, list) else str(value)
            body.append(_block(f"- *{label}:*", shown))
    for q in d.get("quotes") or []:
        if isinstance(q, dict):
            body.append(_block(f"- *Your words, {q.get('said', '')}:*", f'"{q.get("words", "")}" ({q.get("context", "")})'))
    return head, body + _mentions(spec, iid, body)


def _block(prefix: str, text: str) -> str:
    lines = str(text).strip().splitlines() or [""]
    indent = "  " if prefix.startswith("-") else "> " if prefix == ">" else "  "
    first = f"{prefix} {lines[0]}".rstrip()
    return "\n".join([first] + [f"{indent}{ln}" if ln else (">" if prefix == ">" else "") for ln in lines[1:]])


def _mentions(spec: Spec, iid: str, body: list[str]) -> list[str]:
    seen = [m for m in dict.fromkeys(_MENTION.findall("\n".join(body))) if m != iid and m in spec.items]
    labelled = {m for line in body if "*Under:*" in line or "*Verifies:*" in line or line.startswith("  - ")
                for m in _MENTION.findall(line.split(":")[0] if line.startswith("  - ") else line)}
    rest = [m for m in seen if m not in labelled]
    return [f"- *Mentioned:* {'; '.join(_label(spec, m) for m in rest)}"] if rest else []


def _alterations_section(spec: Spec, change: Change) -> list[str]:
    """CHANGE-14: what this change altered among the items the engineer approved, wrote or decided."""
    alts = review.alterations(spec, change)
    if not alts:
        return []
    out = ["## Alterations awaiting your answer", ""]
    pending = [a for a in alts if not a["answered"] and not a["removed"]]
    out += (["This change altered items you locked, wrote or decided. Keep each one with the line shown, or ask "
             "for it to be rolled back.", ""] if pending else ["None left.", ""])
    for a in pending:
        head, body = _full(spec, a["id"])
        out += [f"### {head}", "", f"**Why you're asked:** {' and '.join(a['reasons'])}. Keep it: `{a['id']} LGTM`", ""]
        for e in a["entries"]:
            out.append(f"- *Changed because:* {e.get('reason', '')}")
            before, after = e.get("before") or {}, e.get("after") or {}
            for key in dict.fromkeys(list(before) + list(after)):
                if key in before:
                    out.append(_block(f"  - *{key}, before:*", _one_line(before[key])))
                if key in after:
                    out.append(_block(f"  - *{key}, now:*", _one_line(after[key])))
        if any("text" in (e.get("after") or {}) for e in a["entries"]):
            body = [line for line in body if not line.startswith(">")]  # the new text is shown just above
        out += [*body, ""]
    removed = [a["id"] for a in alts if a["removed"]]
    if removed:
        out += [f"*Removed:* {', '.join(removed)}. Say if any should come back.", ""]
    answered = [f"{a['id']} ({'rolled back' if a['rolled_back'] else 'kept'})" for a in alts if a["answered"]]
    if answered:
        out += [f"*Answered:* {', '.join(answered)}", ""]
    return out


def _proposals_section(spec: Spec, change: Change) -> list[str]:
    """CHANGE-15: items proposed for the engineer's explicit approval, each readable on the spot (REVIEW-18)."""
    proposals = change.data.get("proposals") or []
    if not proposals:
        return []
    out, pending, done = ["## Proposed for you to lock", ""], [], []
    for p in proposals:
        ids = [i for i in p.get("ids") or [] if review.kind_and_data(spec, i) and i not in withdrawn_from(p)]
        for iid in ids:
            if review.state_of(spec, iid).state == review.APPROVED:
                done.append(iid)
                continue
            pending.append(iid)
            head, body = _full(spec, iid)
            out += [f"### {head}", "", f"**Why I'm asking:** {p.get('why', '')}", "", *body, ""]
    if not pending and not done:  # every proposal withdrawn (CHANGE-28)
        return []
    if pending:
        out += [f"To lock every item above: `lock {', '.join(pending)}`", ""]
    if done:
        out += [f"*Already locked:* {', '.join(_label(spec, i) for i in done)}", ""]
    return out


def _one_line(value) -> str:
    if isinstance(value, list):
        return ", ".join(_quote_line(v) if isinstance(v, dict) else str(v) for v in value)
    return " ".join(str(value).split())


def _quote_line(q: dict) -> str:
    """A record on one line: an intent record's summary with who, when and why (MODEL-36), or an older quote."""
    context = " ".join(str(q.get("context", "")).split())
    if "basis" in q:
        said = " ".join(str(q.get("said", "")).split())
        return f"{q.get('basis')} by {q.get('by', '')}, {q.get('when', '')}: {said} ({context})"
    words = " ".join(str(q.get("words", "")).split())
    return f"\"{words}\" ({q.get('said', '')}; {context})"


