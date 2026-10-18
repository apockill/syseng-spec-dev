"""Change records (CHANGE): what was asked, in which mode, what changed in the spec and why,
and the open decisions waiting for the engineer.

A change record is spec/changes/<date>-round-<N>[-<slug>].yaml, with a generated Markdown view
beside it. At most one change is open at a time; `spec edit` logs every edit into it with its
reason (CHANGE-5). Older rounds were hand-written Markdown and stay as they are.
"""

import datetime
import re
from dataclasses import dataclass
from pathlib import Path

from syseng import review, yamlio
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
    change = Change(changes_dir(spec) / f"{name}.yaml", {
        "request": request, "mode": mode, "target": target, "status": "open", "opened": today,
        "entries": [], "decisions": [], "friction": []})
    change.save()
    return change


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:40]


def close(change: Change) -> None:
    change.data["status"] = "closed"
    change.data["closed"] = datetime.date.today().isoformat()
    change.save()


def add_decision(change: Change, decision: dict) -> str:
    """Adds an open decision (CHANGE-3). It must offer options, one of them recommended (CHANGE-10)."""
    options = decision.get("options") or []
    if not decision.get("question"):
        raise ChangeError("a decision needs a `question`")
    if len(options) < 2:
        raise ChangeError("a decision needs at least two `options` (CHANGE-10)")
    if sum(1 for o in options if o.get("recommended")) != 1:
        raise ChangeError("mark exactly one option `recommended: true` (CHANGE-10)")
    if not decision.get("importance"):
        raise ChangeError("say why this decision ranks where it does, in `importance` (AGENT-40)")
    decisions = change.data.setdefault("decisions", [])
    did = f"D{len(decisions) + 1}"
    entry = {"id": did, "question": decision["question"], "importance": decision["importance"],
             "involves": decision.get("involves") or [], "options": options, "status": "open"}
    decisions.append(entry)
    change.save()
    return did


def resolve(change: Change, ids: list[str], words: str, option: int | None) -> list[str]:
    """Records the engineer's choice. With no option, takes the recommended one (CHANGE-12)."""
    by_id = {d["id"]: d for d in change.data.get("decisions") or []}
    unknown = [i for i in ids if i not in by_id]
    if unknown:
        raise ChangeError(f"unknown decisions: {', '.join(unknown)}")
    done = []
    for i in ids:
        d = by_id[i]
        opts = d.get("options") or []
        chosen = (opts[option - 1] if option else next(o for o in opts if o.get("recommended")))
        d.update({"status": "resolved", "chosen": chosen.get("label"), "words": words,
                  "resolved": datetime.date.today().isoformat()})
        done.append(i)
    change.save()
    return done


def log_friction(change: Change, workaround: str, proposal: str) -> None:
    """AGENT-46: an agent reports a workaround, with a proposed improvement."""
    change.data.setdefault("friction", []).append({"workaround": workaround, "proposal": proposal})
    change.save()


def add_proposal(change: Change, ids: list[str], why: str) -> None:
    """SYS-38: an agent proposes items for the engineer's explicit approval, saying why they deserve it."""
    if not (why or "").strip():
        raise ChangeError("say why these items deserve the engineer's attention (AGENT-40)")
    change.data.setdefault("proposals", []).append(
        {"ids": ids, "why": why, "proposed": datetime.datetime.now().astimezone().isoformat(timespec="minutes")})
    change.save()


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
        out += ["", f"To accept every recommendation: `spec resolve {' '.join(x['id'] for x in open_ds)} "
                    f"--words \"<your words>\"`.", ""]
    out += _alterations_section(spec, change) + _proposals_section(spec, change)
    resolved = [x for x in decisions if x.get("status") == "resolved"]
    if resolved:
        out += ["## Resolved decisions", ""]
        out += [f"- **{x['id']}:** {x.get('question', '')} → {x.get('chosen', '')} ({x.get('words', '')})"
                for x in resolved]
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
        out += ["", "## Agent friction (AGENT-46)", ""]
        out += [f"- **Worked around:** {f.get('workaround', '')} **Proposal:** {f.get('proposal', '')}"
                for f in friction]
    return "\n".join(out).rstrip("\n") + "\n"


def _is_block(value) -> bool:
    return isinstance(value, str) and "\n" in value.strip()


def _alterations_section(spec: Spec, change: Change) -> list[str]:
    """CHANGE-14: what this change altered among the items the engineer approved, wrote or decided."""
    alts = review.alterations(spec, change)
    if not alts:
        return []
    out = ["## Alterations awaiting your answer", ""]
    pending = [a for a in alts if not a["answered"] and not a["removed"]]
    if pending:
        out += ["This change altered items you approved, wrote or decided. Keep each one with the line shown, "
                "or ask for it to be rolled back.", ""]
    else:
        out += ["None left.", ""]
    for a in pending:
        out.append(f"- **{_label(spec, a['id'])}**, because {' and '.join(a['reasons'])}. Keep it: "
                   f"`{a['id']} LGTM`")
        out += [f"  - {e.get('reason', '')}" for e in a["entries"]]
    removed = [a["id"] for a in alts if a["removed"]]
    if removed:
        out.append(f"- *Removed:* {', '.join(removed)}. Say if any should come back.")
    answered = [f"{a['id']} ({'rolled back' if a['rolled_back'] else 'kept'})" for a in alts if a["answered"]]
    if answered:
        out.append(f"- *Answered:* {', '.join(answered)}")
    return out + [""]


def _proposals_section(spec: Spec, change: Change) -> list[str]:
    """CHANGE-15: items an agent proposed for the engineer's explicit approval, in the order proposed."""
    proposals = change.data.get("proposals") or []
    if not proposals:
        return []
    out, pending = ["## Proposed for your explicit approval", ""], []
    for p in proposals:
        ids = [i for i in p.get("ids") or [] if review.kind_and_data(spec, i)]
        waiting = [i for i in ids if review.state_of(spec, i).state != review.APPROVED]
        pending += [i for i in waiting if i not in pending]
        done = "" if waiting else " *(approved)*"
        out.append(f"- {', '.join(_label(spec, i) for i in ids)}: {p.get('why', '')}{done}")
    if pending:
        out += ["", f"To approve the ones still waiting: `approve {', '.join(pending)}`"]
    return out + [""]


def _one_line(value) -> str:
    if isinstance(value, list):
        return ", ".join(_quote_line(v) if isinstance(v, dict) else str(v) for v in value)
    return " ".join(str(value).split())


def _quote_line(q: dict) -> str:
    """A quote on one line: the engineer's words, then when and about what (MODEL-36)."""
    words = " ".join(str(q.get("words", "")).split())
    return f"\"{words}\" ({q.get('said', '')}; {' '.join(str(q.get('context', '')).split())})"


def write_views(spec: Spec) -> list[Path]:
    written = []
    for change in all_changes(spec):
        path = change.path.with_suffix(".md")
        text = view(spec, change)
        if not path.exists() or path.read_text() != text:
            path.write_text(text)
            written.append(path)
    return written
