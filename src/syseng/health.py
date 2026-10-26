"""Measures of a spec's health, for the overview the review page opens on (REVIEW-32, DR-69).

Each measure says which direction is better, so a comparison can mark the ones that got worse.
`spec review --section overview` prints the same numbers for agents (SYS-47).
"""

from syseng import levels, review
from syseng.model import Spec

# key, label, which direction is better ("up", "down", or None when it isn't better either way), shown as a tile
MEASURES = [
    ("coverage", "Verification coverage", "up", True),
    ("unverified", "Requirements without verification", "down", True),
    ("tests", "Linked tests", "up", True),
    ("stale", "Changed since a person gave it", "down", True),
    ("awaiting", "Waiting for your answer", "down", True),
    ("errors", "Checker errors", "down", True),
    ("todos", "Checker to-dos", "down", False),
    ("unserved", "Needs nothing serves", "down", False),
    ("flow", "Requirements skipping a level", "down", False),
    ("locked", "Items a person locked", None, False),
    ("added", "Items an agent added unasked", None, False),
    ("needs", "Needs", None, False),
    ("requirements", "Requirements", None, False),
    ("vis", "Verification items", None, False),
    ("decisions", "Decision records", None, False),
    ("elements", "System elements", None, False),
    ("links", "Trace links", None, False),
    ("dependencies", "Element dependencies", None, False),
]


def metrics(spec: Spec) -> dict:
    from syseng import check
    reqs = spec.requirements()
    vis = spec.of_kind("vi")
    verified = {r for v in vis for r in (v.data.get("verifies") or [])}
    unverified = sum(1 for r in reqs if r.id not in verified and not r.data.get("verification_deferred"))
    findings = check.check(spec)
    ids = list(spec.items) + list(spec.elements)
    lv = {i: levels.level_of(spec, i) for i in ids}
    mix = {name: 0 for name in levels.ORDER}  # the readable layers: needs and requirements
    for item in spec.of_kind("need") + reqs:
        mix[lv[item.id].level] += 1
    return {
        "coverage": round(100 * (len(reqs) - unverified) / len(reqs), 1) if reqs else 100.0,
        "unverified": unverified,
        "tests": sum(len(links or []) for v in vis for links in (v.data.get("tests") or {}).values()),
        "stale": sum(1 for x in lv.values() if x.stale),
        "awaiting": len(review.unanswered(spec)) + sum(
            1 for c in _changes(spec) for d in c.data.get("decisions") or [] if d.get("status") == "open"),
        "errors": sum(1 for f in findings if f.severity == "error"),
        "todos": sum(1 for f in findings if f.severity == "todo"),
        "unserved": sum(1 for f in findings if f.code == "T002"),
        "flow": sum(1 for f in findings if f.code == "T005"),
        "locked": sum(1 for x in lv.values() if x.level == levels.EXPLICIT),
        "added": sum(1 for x in lv.values() if x.level == levels.ADDED),
        "needs": len(spec.of_kind("need")),
        "requirements": len(reqs),
        "vis": len(vis),
        "decisions": len(spec.of_kind("decision")),
        "elements": len(spec.elements),
        "links": sum(len(review.parents(spec, i)) for i in ids),
        "dependencies": sum(len(e.depends_on) for e in spec.elements.values()),
        "mix": mix,
    }


def _changes(spec: Spec):
    from syseng import changes
    return changes.all_changes(spec)


def compare(now: dict, was: dict | None) -> list[dict]:
    """Each measure with its value now and before, and whether it got worse: the worse ones first."""
    out = []
    for key, label, better, tile in MEASURES:
        before = (was or {}).get(key)
        delta = None if before is None else round(now[key] - before, 1)
        worse = bool(delta and better and ((delta < 0) if better == "up" else (delta > 0)))
        improved = bool(delta and better and not worse)
        out.append({"key": key, "label": label, "now": now[key], "was": before, "delta": delta, "better": better,
                    "worse": worse, "improved": improved, "tile": tile, "percent": key == "coverage"})
    return sorted(out, key=lambda m: (not m["worse"], not m["tile"]))
