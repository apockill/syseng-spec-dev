"""Renders the spec as the Markdown views the engineer reads (REVIEW-14).

The views are generated, never hand-edited: `spec check` reports a view that no longer
matches the spec (R001). The requirements view reads top-down: needs, then system
requirements, then each system element.
"""

from pathlib import Path

from syseng import changes, review
from syseng.model import Item, Spec

MARK = {"engineer": "✅", "agent": "🟡"}
SUBFIELDS = [  # (data key, label) in display order
    ("source", "Source"), ("refines", "Refines"), ("why", "Why"),
    ("context", "Context (paraphrased)"), ("reworded", "Reworded"), ("allocation_note", "Also allocated to"),
]


def views(spec: Spec) -> dict[str, str]:
    out = {"requirements.md": requirements_view(spec), "decisions.md": decisions_view(spec)}
    for change in changes.all_changes(spec):
        out[f"changes/{change.path.with_suffix('.md').name}"] = changes.view(spec, change)
    return out


def write_views(spec: Spec) -> list[Path]:
    written = []
    for name, text in views(spec).items():
        path = spec.root / name
        if not path.exists() or path.read_text() != text:
            path.write_text(text)
            written.append(path)
    return written


# ---------------------------------------------------------------- helpers
def _marks(spec: Spec, item: Item) -> str:
    """Whose words an item is, and its review state (REVIEW-16)."""
    mark = MARK.get(item.data.get("origin") or item.data.get("decided_by"), "❔")
    s = review.state_of(spec, item.id)
    state = {review.APPROVED: " 🔒", review.CHANGED: " 🔓", review.DELEGATED: f" ⤷{s.under}"}.get(s.state, "")
    return mark + state


def _quote_lines(item: Item) -> list[str]:
    """The engineer's exact words, with when they said them and what was being discussed (REVIEW-17)."""
    out = []
    for q in item.data.get("quotes") or []:
        if isinstance(q, dict):
            out += _indent_block(f"\"{q.get('words', '')}\"", f"  - *Your words, {q.get('said', '')}:* ", "    ")
            if q.get("context"):
                out.append(f"    *({q['context']})*")
    return out


def _indent_block(text: str, first_prefix: str, rest_indent: str) -> list[str]:
    lines = str(text).split("\n")
    return [first_prefix + lines[0]] + [rest_indent + ln if ln else "" for ln in lines[1:]]


def _id_key(s: str):
    head, _, num = s.rpartition("-")
    digits = num.lstrip("V")
    return (head, int(digits) if digits.isdigit() else 0)


def _children(spec: Spec) -> dict[str, list[str]]:
    kids: dict[str, list[str]] = {}
    order = {e: i for i, e in enumerate(spec.element_order())}
    for item in spec.of_kind("requirement"):
        parent = item.data.get("traces_to")
        if parent:
            kids.setdefault(parent, []).append(item.id)
    for v in kids.values():
        v.sort(key=lambda i: (order.get(spec.items[i].element, 99), _id_key(i)))
    return kids


def _item_lines(spec: Spec, item: Item, children: dict[str, list[str]]) -> list[str]:
    d = item.data
    if item.kind == "need":
        head = f"- {_marks(spec, item)} **{item.id}** {d.get('text', '')}"
    else:
        ups = d.get("serves") if item.kind in ("system", "constraint") else (
            [d["traces_to"]] if d.get("traces_to") else [])
        if d.get("derived"):
            ups = ["derived"]
        arrow = f" ↑{', '.join(ups)}" if ups else ""
        head = f"- {_marks(spec, item)} **{item.id}**{arrow} · {d.get('text', '')}"
    lines = [head] + _quote_lines(item)
    for key, label in SUBFIELDS:
        if d.get(key):
            lines += _indent_block(d[key], f"  - *{label}:* ", "    ")
    if item.kind == "system" and children.get(item.id):
        lines.append(f"  - *Refined by:* {', '.join(children[item.id])}")
    return lines


def _counts(spec: Spec) -> str:
    needs = spec.of_kind("need")
    system = spec.of_kind("system")
    constraints = spec.of_kind("constraint")
    element_reqs = spec.of_kind("requirement")
    all_items = needs + system + constraints + element_reqs
    confirmed = sum(1 for i in all_items if i.data.get("origin") == "engineer")
    states = [review.state_of(spec, i.id).state for i in all_items]
    top = len(needs) + len(system) + len(constraints)
    return (f"**{len(needs)} needs · {len(system)} system requirements · {len(constraints)} constraints · "
            f"{len(element_reqs)} system-element requirements** ({confirmed} confirmed, "
            f"{len(all_items) - confirmed} need review; {states.count(review.APPROVED)} approved, "
            f"{states.count(review.CHANGED)} changed since approval, {states.count(review.DELEGATED)} delegated, "
            f"{states.count(review.UNREVIEWED)} unreviewed). The layer to read is the first three: {top} items.")


def _latest_change(spec: Spec) -> str | None:
    stems = {p.stem for p in (spec.root / "changes").glob("*") if p.suffix in (".md", ".yaml")}
    latest = sorted(stems, key=_change_key)
    return f"{latest[-1]}.md" if latest else None


def _change_key(name: str):
    import re
    m = re.search(r"round-(\d+)", name)
    return (name[:10], int(m.group(1)) if m else 0, name)


# ---------------------------------------------------------------- requirements view
INTRO = """Read top-down. The **needs** say what you want, and the **system requirements** say what the toolkit as a whole shall do; together they're the layer to read. Drill into a system element only where you care.

- ✅ **CONFIRMED**: from your words. *Your words* lines quote you exactly, with when you said them and what we were discussing. Older items quote you under *Source*, with typos fixed; "…" marks a cut and [brackets] a substitution.
- 🟡 **NEEDS REVIEW**: I added it, or I added substance to something you asked for (a number, a mechanism, a scope). *Why* gives my reasoning; *Refines* names the ask it builds on.
- 🔒 **APPROVED**: you approved this exact text (see [approvals.yaml](approvals.yaml)).
- 🔓 **CHANGED**: you approved an earlier version, and it has changed since.
- ⤷ **DELEGATED**: not approved itself, but under the item named, which you approved. An agent may change it while that item still holds.
- **↑** marks what an item traces to: a requirement's parent, or the needs a system requirement serves."""


def requirements_view(spec: Spec) -> str:
    out: list[str] = ["# Requirements", ""]
    out.append("*Generated by `spec render` from `spec/elements/`. Don't edit this file by hand: "
               "change the spec with `spec edit`, which re-renders it.*")
    out.append("")
    latest = _latest_change(spec)
    if latest:
        out.append(f"- **Latest change:** [changes/{latest}](changes/{latest})")
    out += ["- **Why things are the way they are:** [decisions.md](decisions.md), the decision records",
            "- **What you've approved:** [approvals.yaml](approvals.yaml)",
            "- **Vocabulary:** [glossary.md](glossary.md)", "", "## How to read this", "", INTRO, "",
            _counts(spec), "", "## Open questions", ""]
    open_qs = [q for q in spec.questions if q.get("status") == "open"]
    if open_qs:
        for q in open_qs:
            out += _indent_block(q.get("question", ""), f"{q['id'][1:]}. ", "    ")
        out.append("")
    else:
        out += ["None right now.", ""]
    resolved = [q for q in spec.questions if q.get("status") == "resolved"]
    if resolved:
        out += ["### Resolved", "", "| Q | Round | Resolution | Items |", "|---|---|---|---|"]
        out += [f"| {q['id'][1:]} | {q.get('round', '')} | {q.get('resolution', '')} | {q.get('items', '')} |"
                for q in resolved]
        out.append("")
    out += ["---", ""]
    children = _children(spec)
    sections = [
        ("Needs", "What you want, in your terms. You validate these; nothing verifies them.", ["need"]),
        ("System requirements", "What the toolkit as a whole shall do. Each one serves the needs marked ↑ "
                                "and is refined by the system-element requirements listed under it.", ["system"]),
        ("Constraints", "Limits you've put on the solution. They're verified directly and aren't refined further.",
         ["constraint"]),
    ]
    for title, intro, kinds in sections:
        items = sorted(spec.of_kind(*kinds), key=lambda i: _id_key(i.id))
        out += [f"## {title}", "", intro, ""]
        for item in items:
            out += _item_lines(spec, item, children)
        out.append("")
    out += ["---", "", "## System elements", "", "| ID | System element | Parent | Depends on |", "|---|---|---|---|"]
    for eid in spec.element_order():
        e = spec.elements[eid]
        out.append(f"| {eid} | {e.title} | {e.parent or '—'} | {', '.join(e.depends_on) or '—'} |")
    out.append("")
    for eid in spec.element_order():
        e = spec.elements[eid]
        items = [i for i in spec.of_kind("requirement") if i.element == eid]
        retired = [r for r in spec.retired if r.get("element") == eid]
        if not items and not retired:
            continue
        depth_child = e.parent and spec.elements.get(e.parent) and spec.elements[e.parent].parent
        heading = f"### {eid}: {e.title} (child of {e.parent})" if depth_child else f"## {eid}: {e.title}"
        out += [heading, ""]
        if e.data.get("purpose"):
            out += [str(e.data["purpose"]), ""]
        if e.data.get("note"):
            out += [f"*{e.data['note']}*", ""]
        ordered = ([i for i in items if i.data.get("origin") == "engineer"]
                   + [i for i in items if i.data.get("origin") != "engineer"])
        for item in ordered:
            out += _item_lines(spec, item, children)
        if retired:
            out.append("- *Removed:*")
            out += [f"  - {r.get('note', ', '.join(r.get('ids', [])))}" for r in retired]
        out.append("")
    return "\n".join(out).rstrip("\n") + "\n"


# ---------------------------------------------------------------- decisions view
DECISIONS_INTRO = """*Generated by `spec render` from the `decisions.yaml` file of each system element. Don't edit this file by hand.*

These are the decisions made while designing and building the toolkit, each attached to the system elements it affects. Reasoning is paraphrased, not quoted.

- ✅ marks a decision you made.
- 🟡 marks a decision an agent made, which needs your review.
- 🔒 marks a decision you've approved, 🔓 one that changed since you approved it, and ⤷ one delegated under an item you approved."""

DECISION_FIELDS = [("status", "Status"), ("context", "Context"), ("decision", "Decision"),
                   ("alternatives", "Alternatives"), ("consequences", "Consequences")]


def decisions_view(spec: Spec) -> str:
    out = ["# Decision records", "", DECISIONS_INTRO, ""]
    for item in sorted(spec.of_kind("decision"), key=lambda i: _id_key(i.id)):
        d = item.data
        out.append(f"### {item.id} {_marks(spec, item)} {d.get('title', '')}")
        out.append(f"*System elements:* {', '.join(d.get('elements') or [])} · "
                   f"*Requirements:* {d.get('requirements', '')} · *Recorded:* {d.get('recorded', '')}")
        for key, label in DECISION_FIELDS:
            if d.get(key):
                out += _indent_block(d[key], f"- **{label}:** ", "  ")
        out.append("")
    return "\n".join(out).rstrip("\n") + "\n"
