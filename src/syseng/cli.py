"""The `spec` command (CLI-1).

  spec check [--merge] [--todo] [--json]   report everything unfinished (CHECK-1)
  spec render                               regenerate the Markdown views
  spec show ID                              one item with its trace, children and approval
  spec approve ID... --words TEXT           record the engineer's approval (AGENT-21)

Run from anywhere inside a repository that has spec/toolkit.yaml, or pass --spec DIR.
"""

import argparse
import datetime
import json
import re
import sys
from pathlib import Path

from syseng import check as checker
from syseng import fingerprint, model, render, yamlio


def _load(args) -> model.Spec:
    root = Path(args.spec) if args.spec else model.find_spec_root(Path.cwd())
    if root is None or not (root / "toolkit.yaml").exists():
        sys.exit("spec: no spec/toolkit.yaml here or in any parent directory (use --spec DIR)")
    return model.load(root)


def cmd_check(args) -> int:
    spec = _load(args)
    findings = checker.check(spec, merge=args.merge)
    if args.json:
        print(json.dumps([{"code": f.code, "severity": f.severity, "item": f.item, "message": f.message,
                           "file": str(f.file) if f.file else None, "line": f.line} for f in findings], indent=2))
    else:
        text = checker.format_findings(findings, spec.root)
        if text:
            print(text)
        if args.todo:
            for f in (f for f in findings if f.severity == "todo"):
                print(f"todo[{f.code}] {f.message}")
            print()
        print(checker.summarize(findings))
    return 1 if any(f.severity == "error" for f in findings) else 0


def cmd_render(args) -> int:
    spec = _load(args)
    written = render.write_views(spec)
    print("\n".join(f"wrote {p.relative_to(spec.root.parent)}" for p in written) or "views already up to date")
    return 0


def cmd_show(args) -> int:
    spec = _load(args)
    iid = args.id
    if iid in spec.elements:
        e = spec.elements[iid]
        print(f"{iid}: {e.title}  (system element; parent {e.parent or '—'}; depends on {', '.join(e.depends_on) or '—'})")
        print(f"  {e.data.get('purpose', '')}")
        for item in sorted((i for i in spec.items.values() if i.element == iid), key=lambda i: i.id):
            print(f"  {item.id} [{item.kind}] {item.data.get('text') or item.data.get('title') or item.data.get('description', '')}")
        return 0
    item = spec.items.get(iid)
    if item is None:
        retired = [r for r in spec.retired if iid in (r.get("ids") or [])]
        print(f"{iid} was retired: {retired[0].get('note')}" if retired else f"{iid}: no such item")
        return 1
    d = item.data
    status = {s["id"]: s["state"] for s in checker.approval_status(spec)}[iid]
    print(f"{iid} [{item.kind}, in {item.element}, origin {d.get('origin') or d.get('decided_by')}, "
          f"approval: {status}]")
    print(f"  {d.get('text') or d.get('title') or d.get('description', '')}")
    for key in ("source", "why", "refines", "context", "decision"):
        if d.get(key):
            print(f"  {key}: {' '.join(str(d[key]).split())}")
    chain, cur = [], item
    while cur is not None and cur.kind == "requirement" and cur.data.get("traces_to"):
        cur = spec.items.get(cur.data["traces_to"])
        if cur:
            chain.append(cur)
    for up in chain:
        print(f"  ↑ {up.id}: {up.data.get('text', '')}")
    top = chain[-1] if chain else item
    for n in top.data.get("serves") or []:
        need = spec.items.get(n)
        print(f"  ↑ {n}: {need.data.get('text', '') if need else '(missing)'}")
    kids = [i for i in spec.of_kind("requirement") if i.data.get("traces_to") == iid]
    for k in kids:
        print(f"  ↓ {k.id}: {k.data.get('text', '')}")
    if item.kind == "need":
        for r in spec.of_kind("system", "constraint"):
            if iid in (r.data.get("serves") or []):
                print(f"  served by {r.id}: {r.data.get('text', '')}")
    vis = [v for v in spec.of_kind("vi") if iid in (v.data.get("verifies") or [])]
    for v in vis:
        print(f"  verified by {v.id} ({v.data.get('method')}, {v.data.get('technique')}): {v.data.get('description', '')}")
    drs = [x for x in spec.of_kind("decision") if re.search(rf"\b{re.escape(iid)}\b", str(x.data.get("requirements", "")))]
    for x in drs:
        print(f"  decided in {x.id}: {x.data.get('title', '')}")
    return 0


def _expand(ids: list[str]) -> list[str]:
    """Expands ranges such as NEED-1..NEED-12 (or NEED-1..12)."""
    out = []
    for token in ids:
        m = re.fullmatch(r"([A-Z]+-V?)(\d+)\.\.(?:[A-Z]+-V?)?(\d+)", token)
        if m:
            out += [f"{m.group(1)}{n}" for n in range(int(m.group(2)), int(m.group(3)) + 1)]
        else:
            out.append(token)
    return out


def cmd_approve(args) -> int:
    spec = _load(args)
    ids = _expand(args.ids)
    missing = [i for i in ids if i not in spec.items and i not in spec.elements]
    if missing:
        print(f"spec approve: unknown IDs: {', '.join(missing)}; nothing recorded")
        return 1
    today = datetime.date.today().isoformat()
    by_id = {a.get("id"): a for a in spec.approvals}
    for iid in ids:
        if iid in spec.elements:
            kind, data = "element", spec.elements[iid].data
        else:
            kind, data = spec.items[iid].kind, spec.items[iid].data
        by_id[iid] = {"id": iid, "fingerprint": fingerprint.of(kind, data), "approved_on": today,
                      "via": args.via, "words": args.words, "text": fingerprint.summary(kind, data)}
    yamlio.write(spec.root / "approvals.yaml", sorted(by_id.values(), key=lambda a: render._id_key(a["id"])))
    print(f"approved {len(ids)} item{'s' if len(ids) != 1 else ''}")
    render.write_views(model.load(spec.root))
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="spec", description="Systems-engineering spec toolkit")
    parser.add_argument("--spec", help="spec directory (default: find spec/ from here upward)")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("check", help="report everything unfinished in the spec")
    p.add_argument("--merge", action="store_true", help="treat unapproved items as errors (preparing a merge)")
    p.add_argument("--todo", action="store_true", help="also list to-dos")
    p.add_argument("--json", action="store_true", help="machine-readable output")
    p.set_defaults(fn=cmd_check)
    p = sub.add_parser("render", help="regenerate the Markdown views")
    p.set_defaults(fn=cmd_render)
    p = sub.add_parser("show", help="show one item with its trace and approval")
    p.add_argument("id")
    p.set_defaults(fn=cmd_show)
    p = sub.add_parser("approve", help="record the engineer's approval of items")
    p.add_argument("ids", nargs="+", help="IDs, or ranges like NEED-1..NEED-12")
    p.add_argument("--words", required=True, help="the engineer's words, as evidence")
    p.add_argument("--via", default="terminal", help="where the approval was given (terminal, chat, page)")
    p.set_defaults(fn=cmd_approve)
    args = parser.parse_args(argv)
    return args.fn(args)
