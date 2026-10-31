"""Levels of intent: how directly a person asked for each item (SYS-42, DR-54).

  explicit   a person locked it by name (a lock record; today's approvals)
  stated     a person asked for it: what they said, taken alone, says what it requires
  guided     a person's choice or constraint fixed it without saying it
  derived    an item above it needs it, and no person addressed it
  added      an agent added it, and nothing a person locked, stated or guided needs it

An item takes the highest level that applies (CHECK-18). Nothing here is stored: the level is
computed from locks, intent records and the recorded basis each time it's asked for, and the
basis records how an item came about, not how much it matters (SYS-40).

Until the migration (DR-61), older fields are read as well: an engineer origin, a `source` or
`quotes` field, or a decision the engineer made, is stated intent; an agent origin is derived.
"""

from dataclasses import dataclass, field

from syseng import review
from syseng.model import Spec

EXPLICIT, STATED, GUIDED, DERIVED, ADDED = "explicit", "stated", "guided", "derived", "added"
ORDER = (EXPLICIT, STATED, GUIDED, DERIVED, ADDED)  # highest first
RANK = {lvl: len(ORDER) - n for n, lvl in enumerate(ORDER)}
PEOPLE = (EXPLICIT, STATED, GUIDED)  # the levels a person gave
INTENT_BASES = (STATED, GUIDED)      # an intent record's basis (MODEL-37)
ITEM_BASES = (DERIVED, ADDED)        # an item's own basis, without intent or a lock (MODEL-38)
INTENT_FIELDS = ("by", "when", "context", "said", "basis", "fingerprint", "source", "source_path", "source_author")  # MODEL-36, CHECK-20


DECAY = {EXPLICIT: STATED, STATED: GUIDED, GUIDED: DERIVED}  # one step down for a record given for an earlier version


@dataclass
class Level:
    level: str                   # the level that counts now: one lower than given when the item changed since (CHECK-28)
    changed: bool = False        # its content differs from what its newest lock or intent record was given for
    under: str | None = None     # derived or added: the nearest item above that a person locked, stated or guided
    records: list[dict] = field(default_factory=list)  # locks and intent records, oldest first
    newest: dict | None = None   # the newest record with a fingerprint
    given: str | None = None     # when changed: the level the person gave, before it decayed

    @property
    def by_people(self) -> bool:
        return (self.given or self.level) in PEOPLE

    @property
    def stale(self) -> bool:
        return self.given is not None


def when(record: dict) -> str:
    """A record's date and time, comparable across the formats records use."""
    raw = str(record.get("locked_at") or record.get("approved_at") or record.get("approved_on") or record.get("when")
              or "")
    return raw.replace("T", " ")[:16]


def intent_records(data: dict) -> list[dict]:
    recs = data.get("intent") or []
    return [r for r in recs if isinstance(r, dict)] if isinstance(recs, list) else []


def _legacy_stated(kind: str, data: dict) -> bool:
    """Older fields that carry a person's words or decision (DR-61's transitional mapping)."""
    return (kind == "need" and data.get("basis") != DERIVED or data.get("origin") == "engineer" or bool(data.get("quotes"))
            or (kind == "decision" and data.get("decided_by") == "engineer"))


def own(spec: Spec, iid: str) -> tuple[str, list[dict]]:
    """An item's level from its own records, before looking at what's above it."""
    cache = spec.__dict__.setdefault("_own_levels", {})
    if iid in cache:
        return cache[iid]
    kd = review.kind_and_data(spec, iid)
    kind, data = kd if kd else ("", {})
    history = review.history(spec, iid)
    released = bool(history) and bool(sorted(history, key=when)[-1].get("released"))
    locks = [] if released else [dict(a, _record="lock") for a in history if not a.get("released")]
    intents = [dict(r, _record="intent") for r in intent_records(data)]
    records = sorted(locks + intents, key=when)
    if locks:
        level = EXPLICIT
    elif any(r.get("basis") == STATED for r in intents):
        level = STATED
    elif intents:
        level = GUIDED
    elif _legacy_stated(kind, data):
        level = STATED
    elif data.get("basis") in ITEM_BASES:
        level = data["basis"]
    else:
        level = DERIVED  # agent origin, verification items and element definitions (MODEL-40)
    cache[iid] = (level, records)
    return cache[iid]


def _nearest_above(spec: Spec, iid: str, wanted) -> str | None:
    frontier, seen = [iid], {iid}
    while frontier:
        above = [p for f in frontier for p in review.parents(spec, f) if p not in seen]
        for p in above:
            if own(spec, p)[0] in wanted:
                return p
        seen.update(above)
        frontier = above
    return None


def level_of(spec: Spec, iid: str) -> Level:
    cache = spec.__dict__.setdefault("_levels", {})
    if iid in cache:
        return cache[iid]
    level, records = own(spec, iid)
    under = None
    if level == DERIVED:
        # a derived item under an added one counts as added (DR-54)
        first = _nearest_above(spec, iid, (*PEOPLE, ADDED))
        if first and own(spec, first)[0] == ADDED:
            level = ADDED
            under = _nearest_above(spec, first, PEOPLE)
        else:
            under = first
    elif level == ADDED:
        under = _nearest_above(spec, iid, PEOPLE)
    stamped = [r for r in records if r.get("fingerprint")]
    newest = stamped[-1] if stamped else None
    changed = bool(level in PEOPLE and newest and newest.get("fingerprint") != review.current_fingerprint(spec, iid))
    given = level if changed else None
    if changed:  # given for an earlier version and not kept since: it counts one level lower (DR-68)
        level = DECAY[level]
        if level == DERIVED:
            under = _nearest_above(spec, iid, PEOPLE)
    cache[iid] = Level(level, changed, under, records, newest, given)
    return cache[iid]


def last_changed(spec: Spec, iid: str) -> str:
    """When an item's meaning last changed, from the change records ('' when no logged change)."""
    from syseng import fingerprint
    kd = review.kind_and_data(spec, iid)
    fields = set(fingerprint.MEANING_FIELDS.get(kd[0], ())) if kd else set()
    stamps = [str(e.get("at") or "") for _, e in review._edits(spec, iid) if set(e.get("after") or {}) & fields]
    return max(stamps, default="").replace("T", " ")[:16]


def reviews(spec: Spec) -> list[dict]:
    cache = spec.__dict__.get("_reviews")
    if cache is None:
        from syseng import yamlio
        path = spec.root / "reviews.yaml"
        cache = spec.__dict__["_reviews"] = (yamlio.read(path) or []) if path.exists() else []
    return cache


def seen_since(spec: Spec, at: str) -> bool:
    """Whether a review someone sent back was made after a moment: it showed what had changed by then (DR-68)."""
    stamp = str(at or "").replace("T", " ")[:16]
    return bool(stamp) and any(str(r.get("generated") or "").replace("T", " ")[:16] > stamp for r in reviews(spec))


def label(lv: Level) -> str:
    """The level in words, saying when it was given for an earlier version."""
    if not lv.stale:
        return lv.level
    return {EXPLICIT: "locked to an earlier version", STATED: "stated for an earlier version",
            GUIDED: "guided for an earlier version"}[lv.given]


def kept(spec: Spec, iid: str) -> bool:
    """Whether a person has accepted the item as it is now: a lock or intent record matches its content."""
    now = review.current_fingerprint(spec, iid)
    return any(r.get("fingerprint") == now for r in own(spec, iid)[1])


def describe(spec: Spec, iid: str) -> str:
    """The level in a few words, for messages and views."""
    lv = level_of(spec, iid)
    who = (lv.newest or (lv.records[-1] if lv.records else {})).get("by")
    text = label(lv) + (f" by {who}" if who and lv.by_people else "")
    if lv.under:
        text += f", under {lv.under}"
    return text
