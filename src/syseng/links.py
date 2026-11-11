"""Links into the review page, and the agent's look-at-this list (REVIEW-56 to REVIEW-60, CLI-39, CLI-40, DR-84, DR-85).

A link names what it opens in the URL's fragment alone, in letters, digits, `.`, `_`, `~` and `-`: a page published
somewhere that passes on nothing else, such as a Claude artifact, still gets it (DR-84).

  CORE-12                                an item or element, by its ID
  2026-11-10-round-67-deep-links.D3      a decision: its change record's ID, a dot, D<n>
  2026-11-10-round-67-deep-links.F2      a comment from the person's feedback, the same way
  round-67.D3, D3, F2                    shorter forms the page also takes, while they name only one
  focus~CORE-12~round-67.D3              only these, in this order, with a way back to everything

The page resolves each form with the table `index` builds, so the page and `spec review --link` can't disagree.
"""

import re

from syseng import changes
from syseng.model import Spec

FOCUS = "focus"
SEPARATOR = "~"
ANCHOR_CHARS = re.compile(r"[A-Za-z0-9._~-]+")
_RECORD = re.compile(r"(?:(.+?)[/. ])?([DF])(\d+)")
_FIELD = {"D": ("decisions", "id"), "F": ("feedback", "n")}


class LinkError(Exception):
    pass


def anchor(ref: str) -> str:
    """The fragment that opens what a stored reference names: an item's ID, or `<change>/D<n>` with a dot."""
    return ref.replace("/", ".")


def focus(anchors: list[str]) -> str:
    return SEPARATOR.join([FOCUS, *anchors])


def _records(change: changes.Change, letter: str) -> list[dict]:
    field, key = _FIELD[letter]
    return [r for r in change.data.get(field) or [] if str(r.get(key) or "").startswith(letter)]


def _number(record: dict, letter: str) -> str:
    return str(record.get(_FIELD[letter][1]))


def resolve(spec: Spec, token: str, default: changes.Change | None = None) -> str:
    """The stored reference a target names: an item's ID, or `<change>/D<n>` / `<change>/F<n>` (CLI-39, CLI-40).

    A decision or comment is `<change>/D<n>`, `<change>.D<n>` or `<change> D<n>`, where `<change>` is the change
    record's ID or a part naming only it; a bare `D<n>` or `F<n>` is the open change's (else the newest's), the same
    rule `spec resolve` follows (CHANGE-26)."""
    token = token.strip()
    if token in spec.items or token in spec.elements:
        return token
    m = _RECORD.fullmatch(token)
    if not m:
        raise LinkError(f"{token} isn't an item or element of this spec, a decision (D<n>, <change>/D<n>) or a comment "
                        "(F<n>, <change>/F<n>)")
    where, letter, n = m.group(1), m.group(2), f"{m.group(2)}{m.group(3)}"
    default = default or changes.current(spec) or (changes.all_changes(spec) or [None])[-1]
    if letter == "D":
        try:
            change, d = changes.find_decision(spec, f"{where}/{n}" if where else n, default)
        except changes.ChangeError as e:
            raise LinkError(str(e)) from e
        return changes.qualified(change, d["id"])
    every = changes.all_changes(spec)
    if where:
        pool = [c for c in every if c.id == where] or [c for c in every if re.search(rf"(^|-){re.escape(where)}($|-)", c.id)]
        if len(pool) != 1:
            raise LinkError(f"{where!r} names {'no change record' if not pool else 'more than one change'}"
                            + (f": {', '.join(c.id for c in pool)}; use the full ID" if pool else ""))
        change = pool[0]
    else:
        change = default
    if change is None or not any(_number(f, letter) == n for f in _records(change, letter)):
        raise LinkError(f"{change.id if change else 'the open change'} has no comment {n}; name one of another change "
                        "as <change>/F<n>")
    return changes.qualified(change, n)


def index(spec: Spec) -> dict:
    """What the page needs to open any link (REVIEW-56): every decision and comment on record, by its anchor, and
    each shorter form that names only one of them. A short form naming more than one lists them all."""
    every = changes.all_changes(spec)
    newest = changes.current(spec) or (every or [None])[-1]
    targets: dict[str, dict] = {}
    by_round: dict[str, list] = {}
    for c in every:
        m = re.search(r"round-\d+", c.id)
        if m:
            by_round.setdefault(m.group(0), []).append(c)
    aliases: dict[str, list[str]] = {}
    for c in every:
        rnd = re.search(r"round-\d+", c.id)
        short = rnd.group(0) if rnd and len(by_round[rnd.group(0)]) == 1 else None
        for letter in "DF":
            for r in _records(c, letter):
                n = _number(r, letter)
                key = anchor(changes.qualified(c, n))
                if letter == "D":
                    targets[key] = {"kind": "decision", "change": c.id, "id": n, "status": r.get("status"),
                                    **{k: r.get(k) for k in ("question", "importance", "chosen", "withdrawn_because",
                                                             "involves") if r.get(k)}}
                else:
                    targets[key] = {"kind": "comment", "change": c.id, "id": n,
                                    **{k: r.get(k) for k in ("kind", "comment", "response", "by", "at", "decision")
                                       if r.get(k)}, **({"item": r["id"]} if r.get("id") else {})}
                if short:
                    aliases.setdefault(f"{short}.{n}", []).append(key)
                aliases.setdefault(n, []).append(key)
    for n, keys in list(aliases.items()):  # a bare D<n> or F<n>: the newest change's, the rule the CLI follows
        if len(keys) < 2 or "." in n or newest is None:
            continue
        mine = [k for k in keys if targets[k]["change"] == newest.id]
        others_open = [k for k in keys if k not in mine and targets[k].get("status") == "open"]
        if mine and not others_open:
            aliases[n] = mine
    return {"targets": targets, "aliases": aliases}


# ---------------------------------------------------------------- the look-at-this list (CLI-40, REVIEW-59)
def point(change: changes.Change, refs: list[str], why: str) -> None:
    """Records a look-at-this mark in the open change, after its others: the order recorded is the rank. A target
    marked again moves to the new mark, so marking it again re-ranks it."""
    if not (why or "").strip():
        raise LinkError("say why the engineer should look, with --why")
    _drop(change, refs)
    change.data.setdefault("look_at", []).append({"targets": refs, "why": why, "at": changes._stamp()})
    change.save()


def unpoint(change: changes.Change, refs: list[str]) -> list[str]:
    """Takes targets off the open change's look-at-this list. Returns those that weren't on it."""
    on = {t for m in change.data.get("look_at") or [] for t in m.get("targets") or []}
    _drop(change, refs)
    change.save()
    return [r for r in refs if r not in on]


def _drop(change: changes.Change, refs: list[str]) -> None:
    marks = change.data.get("look_at") or []
    for m in marks:
        m["targets"] = [t for t in m.get("targets") or [] if t not in refs]
    change.data["look_at"] = [m for m in marks if m["targets"]]
    if not change.data["look_at"]:
        change.data.pop("look_at")


def look(spec: Spec) -> dict:
    """The newest change's look-at-this list, the only one the page shows: each change starts clean (REVIEW-60)."""
    every = changes.all_changes(spec)
    newest = changes.current(spec) or (every or [None])[-1]
    if newest is None:
        return {"change": None, "marks": []}
    marks = [{"targets": [{"ref": t, "anchor": anchor(t), "kind": "decision" if "/D" in t else "comment" if "/F" in t
                           else "item"} for t in m.get("targets") or []],
              "why": m.get("why", ""), "at": m.get("at"), "focus": focus([anchor(t) for t in m.get("targets") or []])}
             for m in newest.data.get("look_at") or []]
    return {"change": newest.id, "marks": marks}
