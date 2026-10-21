"""Comparing two versions of the spec, item by item (DIFF, SYS-48, DR-59).

One library serves agents and people alike: `spec diff` prints what it returns as text or YAML,
and the review page renders the same data (SYS-47).

  versions   the working tree, any revision version control can name, or a person's last review
  branches   compared against the merge base with the newer side, so newer work on the branch
             doesn't show up reversed (DIFF-2)
  classes    each differing item gets every one that applies: added, removed, moved, changed in
             meaning, reworded, changed in intent only, or changed only in fields that carry no
             meaning, such as a rationale or a test link (DIFF-3)
  reasons    taken from the change records the newer side adds (DIFF-4)
  levels     each item's level of intent on both sides (DIFF-5)

Reading an older version never touches the working tree (DIFF-1): it's extracted from version
control into a temporary directory.
"""

import io
import subprocess
import tarfile
import tempfile
from dataclasses import asdict, dataclass, field
from pathlib import Path

from syseng import changes, fingerprint, levels, model, review
from syseng.model import Spec

ADDED, REMOVED, MOVED, MEANING, REWORDED, INTENT, DETAILS = (
    "added", "removed", "moved", "meaning", "reworded", "intent", "details")
CLASS_WORDS = {ADDED: "added", REMOVED: "removed", MOVED: "moved", MEANING: "changed in meaning",
               REWORDED: "reworded", INTENT: "changed in intent only", DETAILS: "changed in details only"}
INTENT_FIELDS = {"intent", "basis", "origin", "source", "quotes", "refines"}  # how directly a person asked for it


class DiffError(Exception):
    pass


# ---------------------------------------------------------------- versions
@dataclass
class Version:
    label: str            # what the person asked for: "working tree", "main", "abc1234", "last review"
    revision: str | None  # the commit compared, or None for the working tree
    note: str = ""        # how the label was resolved, such as "merge base of main and HEAD"


def _git(repo: Path, *args: str) -> str:
    try:
        run = subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired) as e:
        raise DiffError(f"can't run git: {e}") from e
    if run.returncode != 0:
        raise DiffError(run.stderr.strip() or f"git {' '.join(args)} failed")
    return run.stdout.strip()


def _exists(repo: Path, ref: str) -> bool:
    try:
        _git(repo, "rev-parse", "--verify", "--quiet", ref)
        return True
    except DiffError:
        return False


def _branch(repo: Path, name: str) -> tuple[str | None, str]:
    """The ref a branch name means, and a note when it was only found on a remote. HEAD, tags and commits
    aren't branches, so a name that resolves as one of those first isn't looked for on a remote."""
    for ref in (f"refs/heads/{name}", f"refs/remotes/{name}"):
        if _exists(repo, ref):
            return ref, ""
    if name != "HEAD" and not _exists(repo, f"{name}^{{commit}}") and _exists(repo, f"refs/remotes/origin/{name}"):
        return f"refs/remotes/origin/{name}", f"{name} exists only as origin/{name}; compared with that"
    return None, ""


def resolve(repo: Path, label: str, newer: str | None = None) -> Version:
    """The revision a label names. A branch resolves to its merge base with the newer side (DIFF-2)."""
    ref, note = _branch(repo, label)
    if ref:
        base = _git(repo, "merge-base", ref, newer or "HEAD")
        short = _git(repo, "rev-parse", "--short", base)
        return Version(label, base, "; ".join(n for n in (note, f"merge base of {label} and {newer or 'HEAD'}, "
                                                               f"{short}") if n))
    try:
        rev = _git(repo, "rev-parse", "--verify", "--quiet", f"{label}^{{commit}}")
    except DiffError:
        raise DiffError(f"{label!r} names no branch, tag or commit here") from None
    return Version(label, rev, _git(repo, "rev-parse", "--short", rev))


def load_at(spec_root: Path, revision: str, into: Path) -> Spec:
    """The spec as it was at a revision, extracted into a temporary directory (DIFF-1)."""
    repo = Path(_git(spec_root, "rev-parse", "--show-toplevel"))
    rel = spec_root.resolve().relative_to(repo.resolve()).as_posix()
    try:
        data = subprocess.run(["git", "archive", "--format=tar", revision, rel], cwd=repo, capture_output=True,
                              timeout=60)
    except (OSError, subprocess.TimeoutExpired) as e:
        raise DiffError(f"can't read the spec at {revision}: {e}") from e
    if data.returncode != 0:
        raise DiffError(f"the spec didn't exist at {revision[:12]}: {data.stderr.decode().strip()}")
    with tarfile.open(fileobj=io.BytesIO(data.stdout)) as tar:
        tar.extractall(into, filter="data")
    spec = model.load(into / rel)
    spec.repo = repo
    return spec


# ---------------------------------------------------------------- comparing
@dataclass
class ItemDiff:
    id: str
    kind: str
    element: str | None
    title: str                                   # the item's text or title, newer side first
    classes: list[str]
    before: dict = field(default_factory=dict)   # every field that differs, as it was
    after: dict = field(default_factory=dict)    # and as it is
    level_before: str | None = None
    level_after: str | None = None
    under: str | None = None                     # for a derived or added item, the intent above it
    reasons: list[str] = field(default_factory=list)
    flags: list[str] = field(default_factory=list)


@dataclass
class Diff:
    older: Version
    newer: Version
    items: list[ItemDiff]
    inspected: dict | None = None  # what a caller measured on the older side while it was loaded (REVIEW-32)

    def counts(self) -> dict[str, int]:
        out = {c: 0 for c in CLASS_WORDS}
        for d in self.items:
            for c in d.classes:
                out[c] += 1
        return {c: n for c, n in out.items() if n}

    def by_kind(self) -> dict[str, dict[str, int]]:
        out: dict[str, dict[str, int]] = {}
        for d in self.items:
            for c in d.classes:
                out.setdefault(d.kind, {}).setdefault(c, 0)
                out[d.kind][c] += 1
        return out

    def to_data(self) -> dict:
        return {"older": asdict(self.older), "newer": asdict(self.newer), "counts": self.counts(), "by_kind": self.by_kind(),
                "items": [{k: v for k, v in asdict(d).items() if v not in (None, [], {})} for d in self.items]}


def _all_ids(spec: Spec) -> list[str]:
    return list(spec.items) + list(spec.elements)


def _data(spec: Spec, iid: str) -> dict:
    kd = review.kind_and_data(spec, iid)
    return {k: v for k, v in (kd[1] if kd else {}).items() if k != "id"}


def _title(spec: Spec, iid: str) -> str:
    d = _data(spec, iid)
    return str(d.get("text") or d.get("title") or d.get("description") or d.get("purpose") or "")


def _new_entries(old: Spec, new: Spec) -> dict[str, list[dict]]:
    """The change-log entries the newer side adds, by item: whole new records, and entries added to old ones."""
    known = {c.path.name: len(c.data.get("entries") or []) for c in changes.all_changes(old)}
    out: dict[str, list[dict]] = {}
    for c in changes.all_changes(new):
        for e in (c.data.get("entries") or [])[known.get(c.path.name, 0):]:
            out.setdefault(str(e.get("id")), []).append(e)
    return out


def _locks(spec: Spec, iid: str) -> list:
    return [a.get("fingerprint") for a in review.history(spec, iid)]


def compare(old: Spec, new: Spec, older: Version, newer: Version) -> Diff:
    entries = _new_entries(old, new)
    out = []
    for iid in dict.fromkeys(_all_ids(new) + _all_ids(old)):
        in_old, in_new = review.kind_and_data(old, iid), review.kind_and_data(new, iid)
        before, after = _data(old, iid), _data(new, iid)
        keys = [k for k in dict.fromkeys(list(before) + list(after)) if before.get(k) != after.get(k)]
        locks_changed = in_old and in_new and _locks(old, iid) != _locks(new, iid)
        if not keys and not locks_changed and in_old and in_new:
            continue
        classes = []
        if not in_old:
            classes.append(ADDED)
        elif not in_new:
            classes.append(REMOVED)
        else:
            if review.parents(old, iid) != review.parents(new, iid):
                classes.append(MOVED)
            if fingerprint.of(*in_old) != fingerprint.of(*in_new):
                meaning = set(fingerprint.MEANING_FIELDS[in_new[0]])
                logged = [e for e in entries.get(iid, []) if set(e.get("after") or {}) & meaning]
                declared = bool(logged) and all(e.get("rewording") for e in logged)
                classes.append(REWORDED if declared else MEANING)
            if locks_changed or set(keys) & INTENT_FIELDS:
                classes.append(INTENT)
            if not classes:
                classes.append(DETAILS)
        kind = (in_new or in_old)[0]
        element = (new.items.get(iid) or old.items.get(iid)).element if kind != "element" else iid
        lv_old = levels.level_of(old, iid) if in_old else None
        lv_new = levels.level_of(new, iid) if in_new else None
        d = ItemDiff(id=iid, kind=kind, element=element, title=_title(new if in_new else old, iid),
                     classes=classes,
                     before={k: before[k] for k in keys if k in before},
                     after={k: after[k] for k in keys if k in after},
                     level_before=lv_old.level if lv_old else None, level_after=lv_new.level if lv_new else None,
                     under=lv_new.under if lv_new else None,
                     reasons=[str(e.get("reason")) for e in entries.get(iid, []) if e.get("reason")])
        if lv_old and lv_old.level in (levels.EXPLICIT, levels.STATED) and (MEANING in d.classes or REMOVED in d.classes):
            d.flags.append(f"alters what a person {'locked' if lv_old.level == levels.EXPLICIT else 'stated'}")
        out.append(d)
    _flag_verification_only(old, new, out)
    out.sort(key=lambda d: (_order(new, d), d.id))
    return Diff(older, newer, out)


def _flag_verification_only(old: Spec, new: Spec, out: list[ItemDiff]) -> None:
    """A verification item that changed while the requirements it verifies didn't: where weakening hides (REVIEW-9)."""
    changed = {d.id for d in out if set(d.classes) & {MEANING, REWORDED, ADDED, REMOVED}}
    for d in out:
        if d.kind != "vi" or not set(d.classes) & {MEANING, REWORDED}:
            continue
        verified = set((new.items.get(d.id) or old.items.get(d.id)).data.get("verifies") or [])
        if verified and not verified & changed:
            d.flags.append("verification changed while what it verifies didn't")


def _order(spec: Spec, d: ItemDiff):
    elements = spec.element_order()
    rank = {"need": 0, "system": 1, "constraint": 2, "element": 3, "requirement": 4, "decision": 5, "vi": 6}
    return (elements.index(d.element) if d.element in elements else -1, rank.get(d.kind, 9))


def between(spec: Spec, older: str, newer: str | None = None, inspect=None) -> Diff:
    """The differences from `older` (a revision or branch) to `newer` (a revision, or the working tree)."""
    repo = spec.repo_root()
    newer_v = resolve(repo, newer) if newer else Version("working tree", None)
    older_v = resolve(repo, older, newer_v.revision)
    with tempfile.TemporaryDirectory() as tmp:
        old = load_at(spec.root, older_v.revision, Path(tmp) / "old")
        new = load_at(spec.root, newer_v.revision, Path(tmp) / "new") if newer_v.revision else spec
        d = compare(old, new, older_v, newer_v)
        if inspect is not None:
            d.inspected = inspect(old)
        return d


def last_review(spec: Spec, person: str) -> dict | None:
    """The newest review a person sent back (MODEL-39), from spec/reviews.yaml."""
    from syseng import yamlio
    path = spec.root / "reviews.yaml"
    reviews = [r for r in (yamlio.read(path) or []) if r.get("by") == person] if path.exists() else []
    return max(reviews, key=lambda r: str(r.get("at", ""))) if reviews else None


def since_review(spec: Spec, person: str, inspect=None) -> Diff:
    """What changed since the person's last review: from the revision the page was made from to the working tree."""
    r = last_review(spec, person)
    if r is None:
        raise DiffError(f"{person} hasn't sent back a review yet; compare against a revision instead, such as main")
    d = between(spec, str(r["revision"]), inspect=inspect)
    note = str(r.get("at", ""))
    if r.get("dirty"):  # the page showed uncommitted work: keep only what differs from what it showed (DR-59)
        shown = _shown(spec, r)
        if shown is not None:
            d.items = [x for x in d.items if _differs(spec, x.id, shown)]
            note += "; the page showed uncommitted work, compared with what it showed"
        else:
            note += "; the page showed uncommitted work, so this compares with the commit it was made from"
    d.older = Version("your last review", str(r["revision"]), note)
    return d


def _shown(spec: Spec, review_record: dict) -> dict | None:
    """What a review page showed, per item: the local snapshot when this machine has it, else the fingerprints the
    review recorded."""
    import json
    snap = spec.repo_root() / ".syseng" / "reviews" / f"{review_record.get('review')}.json"
    if snap.exists():
        items = json.loads(snap.read_text()).get("items", {})
        return {i: {"fingerprint": it.get("fingerprint"), "intent": it.get("intent"), "level": it.get("level"),
                    "locks": len(it.get("locks") or [])} for i, it in items.items()}
    prints = review_record.get("fingerprints")
    return {i: {"fingerprint": f} for i, f in prints.items()} if prints else None


def _differs(spec: Spec, iid: str, shown: dict) -> bool:
    was = shown.get(iid)
    if review.kind_and_data(spec, iid) is None:
        return was is not None  # removed since the page showed it; one already gone then isn't news
    if was is None:
        return True
    if was.get("fingerprint") != review.current_fingerprint(spec, iid):
        return True
    if "intent" in was:
        kd = review.kind_and_data(spec, iid)
        lv = levels.level_of(spec, iid)
        return (was.get("intent") != levels.intent_records(kd[1]) or was.get("level") != lv.level
                or was.get("locks") != len(review.history(spec, iid)))
    return False


# ---------------------------------------------------------------- text
def _value(v) -> str:
    if isinstance(v, list):
        return "; ".join(changes._quote_line(x) if isinstance(x, dict) else str(x) for x in v)
    return " ".join(str(v).split())


def to_text(diff: Diff, spec: Spec) -> str:
    """The differences in a form an agent reads at a glance: one block per item, grouped by element."""
    head = f"spec diff: {diff.older.label}" + (f" ({diff.older.note})" if diff.older.note else "")
    head += f" → {diff.newer.label}" + (f" ({diff.newer.note})" if diff.newer.note else "")
    counts = ", ".join(f"{n} {CLASS_WORDS.get(c, c)}" for c, n in diff.counts().items()) or "no differences"
    lines = [head, f"  {counts}", ""]
    current = object()
    for d in diff.items:
        if d.element != current:
            current = d.element
            title = spec.elements[d.element].title if d.element in spec.elements else ""
            lines.append(f"## {d.element}" + (f": {title}" if title else ""))
        level = (d.level_after or "") if d.level_before in (None, d.level_after) else \
            f"{d.level_before} → {d.level_after or 'gone'}"
        lines.append(f"{d.id} [{', '.join(CLASS_WORDS.get(c, c) for c in d.classes)}; {level}] {d.title}")
        for flag in d.flags:
            lines.append(f"  ! {flag}")
        for key in dict.fromkeys(list(d.before) + list(d.after)):
            if key in d.before:
                lines.append(f"  - {key}: {_value(d.before[key])}")
            if key in d.after:
                lines.append(f"  + {key}: {_value(d.after[key])}")
        for r in d.reasons:
            lines.append(f"  why: {r}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"
