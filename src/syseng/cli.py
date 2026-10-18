"""The `spec` command (CLI-1).

  spec check [--merge] [--todo] [--json]   report everything unfinished (CHECK-1)
  spec render                               regenerate the Markdown views
  spec show ID                              one item: trace, children, verification, history
  spec approve ID... --words TEXT [--via]   record the engineer's approval, with who and how (SYS-33)
  spec propose ID... --why TEXT             propose items for the engineer's explicit approval (SYS-38)
  spec change start|close|show              open and close the change record edits are logged in
  spec edit [--dry-run] < edits.yaml        change the spec (CLI-5 to CLI-8)
  spec decide < decision.yaml               add an open decision with options (CHANGE-10)
  spec resolve D1 ... --words TEXT          record the engineer's choice (CHANGE-12)
  spec friction --workaround … --proposal … report friction with the toolkit (AGENT-46)
  spec init [--harness NAME]                set up a repository in one step (SYS-5)

Run from anywhere inside a repository that has spec/toolkit.yaml, or pass --spec DIR.
"""

import argparse
import datetime
import getpass
import json
import re
import subprocess
import sys
from pathlib import Path

from syseng import changes, edit, fingerprint, init, model, render, review, yamlio
from syseng import check as checker


def _load(args) -> model.Spec:
    root = Path(args.spec) if args.spec else model.find_spec_root(Path.cwd())
    if root is None or not (root / "toolkit.yaml").exists():
        sys.exit("spec: no spec/toolkit.yaml here or in any parent directory (use --spec DIR)")
    return model.load(root)


def cmd_check(args) -> int:
    spec = _load(args)
    findings = checker.check(spec)
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
        if args.merge:  # CHECK-15: shows what the engineer may want to answer first; never fails because of it
            pending = review.unanswered(spec)
            print("Before this branch lands, these alterations await the engineer's answer:" if pending
                  else "No alteration awaits the engineer's answer.")
            for cid, alt in pending:
                print(f"  {changes._label(spec, alt['id'])}: {' and '.join(alt['reasons'])}; altered in {cid}. "
                      f"Keep it: `{alt['id']} LGTM`")
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
    print(f"{iid} [{item.kind}, in {item.element}, origin {d.get('origin') or d.get('decided_by')}, "
          f"approval: {review.state_of(spec, iid).state}]")
    print(f"  {d.get('text') or d.get('title') or d.get('description', '')}")
    print(f"  attention: {review.describe(spec, iid)}")
    for a in review.history(spec, iid):
        print(f"  approved {a.get('approved_at') or a.get('approved_on')} by {a.get('by', 'the engineer')} via "
              f"{a.get('via')}: {' '.join(str(a.get('words', '')).split())}")
    for key in ("source", "why", "refines", "context", "decision"):
        if d.get(key):
            print(f"  {key}: {' '.join(str(d[key]).split())}")
    for q in d.get("quotes") or []:
        print(f"  your words, {q.get('said')}: {' '.join(str(q.get('words', '')).split())} "
              f"[{' '.join(str(q.get('context', '')).split())}]")
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
    _print_history(spec, iid)
    return 0


def _print_history(spec: model.Spec, iid: str) -> None:
    """A requirement's history (CLI-3): each logged change with its reason, then older mentions."""
    for change in changes.all_changes(spec):
        for e in change.data.get("entries") or []:
            if e.get("id") == iid:
                print(f"  history: {e.get('op')} in {change.id}: {e.get('reason', '')}")
    yaml_named = {c.path.with_suffix(".md").name for c in changes.all_changes(spec)}
    for md in sorted((spec.root / "changes").glob("*.md")):
        if md.name not in yaml_named and re.search(rf"\b{re.escape(iid)}\b", md.read_text()):
            print(f"  mentioned in changes/{md.name}")


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


def _approver(repo: Path) -> str:
    """CLI-11: the version-control user name, else the login name."""
    try:
        name = subprocess.run(["git", "config", "user.name"], cwd=repo, capture_output=True, text=True,
                              timeout=10).stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        name = ""
    return name or getpass.getuser()


def _settled(spec: model.Spec, iid: str) -> list[str]:
    """CLI-12: the resolved decisions that involved an item, so its approval shows what was discussed first."""
    return [f"{c.id} {d.get('id')}" for c in changes.all_changes(spec) for d in c.data.get("decisions") or []
            if d.get("status") == "resolved" and iid in (d.get("involves") or [])]


def cmd_approve(args) -> int:
    spec = _load(args)
    ids = list(dict.fromkeys(_expand(args.ids)))
    missing = [i for i in ids if i not in spec.items and i not in spec.elements]
    if missing:
        print(f"spec approve: unknown IDs: {', '.join(missing)}; nothing recorded")
        return 1
    now = datetime.datetime.now().astimezone().isoformat(timespec="minutes")
    by = args.by or _approver(spec.root.parent)
    records = list(spec.approvals)  # every approval is kept, oldest first (MODEL-35)
    for iid in ids:
        kind, data = review.kind_and_data(spec, iid)
        record = {"id": iid, "fingerprint": fingerprint.of(kind, data), "approved_at": now, "by": by,
                  "via": args.via, "batch": len(ids), "words": args.words}
        if args.note:
            record["note"] = args.note
        if _settled(spec, iid):
            record["after"] = _settled(spec, iid)
        record["text"] = fingerprint.summary(kind, data)
        records.append(record)
    records.sort(key=lambda a: (render._id_key(a["id"]), str(a.get("approved_at") or a.get("approved_on") or "")))
    yamlio.write(spec.root / "approvals.yaml", records)
    print(f"approved {len(ids)} item{'s' if len(ids) != 1 else ''}:")
    for iid in ids:
        print(f"  {changes._label(spec, iid) if iid in spec.items else f'{iid} ({spec.elements[iid].title})'}")
    render.write_views(model.load(spec.root))
    return 0


def _read_doc(args):
    text = Path(args.file).read_text() if getattr(args, "file", None) else sys.stdin.read()
    try:
        return yamlio.loads(text)
    except Exception as e:  # report YAML problems the same way as any other edit problem
        raise edit.EditError(f"can't read the YAML you sent: {e}") from e


def cmd_change(args) -> int:
    spec = _load(args)
    try:
        if args.action == "start":
            if not args.request:
                print("spec change start: say what the engineer asked for, in a sentence")
                return 1
            c = changes.start(spec, args.request, args.mode, args.target, args.slug)
            print(f"opened {c.id} ({c.data['mode']}, target {c.data['target']}). Every `spec edit` is logged here.")
        elif args.action == "close":
            c = changes.current(spec)
            if c is None:
                print("no change is open")
                return 1
            open_ds = [d["id"] for d in c.data.get("decisions") or [] if d.get("status") == "open"]
            changes.close(c)
            print(f"closed {c.id}" + (f"; open decisions left for the engineer: {', '.join(open_ds)}" if open_ds else ""))
        else:
            c = changes.current(spec)
            if c is None:
                print("no change is open")
                return 0
            print(f"{c.id}: {c.data.get('request', '')} ({c.data.get('mode')}, target {c.data.get('target')}); "
                  f"{len(c.data.get('entries') or [])} edits, "
                  f"{sum(1 for d in c.data.get('decisions') or [] if d.get('status') == 'open')} open decisions")
    except changes.ChangeError as e:
        print(f"spec change: {e}")
        return 1
    render.write_views(model.load(spec.root))
    return 0


def cmd_edit(args) -> int:
    spec = _load(args)
    try:
        doc = edit.load_last(spec.root) if args.retry else _read_doc(args)
        if args.ack:
            doc = edit.with_acks(doc, args.ack)
        result = edit.run(spec.root, doc, dry_run=args.dry_run)
    except (edit.EditError, changes.ChangeError) as e:
        print(f"spec edit: {e}")
        return 1
    print("\n".join(result.context))
    if result.needs_acks:
        edit.save_last(spec.root, doc)
        print("\nThis edit affects approved or depended-on items. Nothing was written. Acknowledge each one by name")
        print("(a line on why the edit is fine for it, or what else must change), then send the batch again with:\n")
        print("acks:")
        for iid, why in result.needs_acks.items():
            print(f"  {iid}: \"<note>\"   # {changes._label(model.load(spec.root), iid)}: {why}")
        retry = " ".join(f"--ack '{iid}=<note>'" for iid in result.needs_acks)
        print(f"\nOr reuse the batch without sending it again: `spec edit --retry {retry}`")
        return 2
    if result.errors:
        edit.save_last(spec.root, doc)
        print("\nThis edit would introduce errors, so nothing was written:\n")
        print(checker.format_findings(result.errors, spec.root))
        return 1
    if not args.dry_run:
        edit.clear_last(spec.root)
    if args.dry_run:
        print("\ndry run: the edit is valid; nothing was written")
        return 0
    print(f"\napplied {len(result.ids)} operation{'s' if len(result.ids) != 1 else ''}: {', '.join(result.ids)}")
    print(checker.summarize(checker.check(model.load(spec.root))))
    return 0


def cmd_status(args) -> int:
    """Where things stand, for an agent starting work or an engineer catching up (CLI-18)."""
    spec = _load(args)
    c = changes.current(spec)
    if c is None:
        print('No change is open. Start one before editing the spec: `spec change start "<what was asked>"`')
    else:
        d = c.data
        entries = d.get("entries") or []
        last = f", last {entries[-1].get('at')}" if entries and entries[-1].get("at") else ""
        print(f"Open change: {c.id} ({d.get('mode')}, target {d.get('target')}), {len(entries)} edits{last}")
        print(f"  asked: {' '.join(str(d.get('request', '')).split())}")
        for x in d.get("decisions") or []:
            if x.get("status") == "open":
                print(f"  open decision {x['id']}: {x.get('question', '')}")
    pending = review.unanswered(spec)
    if pending:
        print("Awaiting the engineer's answer:")
        for cid, alt in pending:
            print(f"  {changes._label(spec, alt['id'])}, altered in {cid}. Keep it: `{alt['id']} LGTM`")
    waiting = [i for ch in changes.all_changes(spec) for p in ch.data.get("proposals") or [] for i in p.get("ids") or []
               if review.kind_and_data(spec, i) and review.state_of(spec, i).state != review.APPROVED]
    if waiting:
        print(f"Proposed for the engineer's approval: `approve {', '.join(dict.fromkeys(waiting))}`")
    print(checker.summarize(checker.check(spec)))
    return 0


def cmd_decide(args) -> int:
    spec = _load(args)
    c = changes.current(spec)
    if c is None:
        print("spec decide: no change is open")
        return 1
    try:
        did = changes.add_decision(c, _read_doc(args) or {})
    except (changes.ChangeError, edit.EditError) as e:
        print(f"spec decide: {e}")
        return 1
    render.write_views(model.load(spec.root))
    print(f"added open decision {did} to {c.id}")
    return 0


def cmd_resolve(args) -> int:
    spec = _load(args)
    c = changes.current(spec) or (changes.all_changes(spec) or [None])[-1]
    if c is None:
        print("spec resolve: no change record found")
        return 1
    try:
        done = changes.resolve(c, args.ids, args.words, args.option)
    except changes.ChangeError as e:
        print(f"spec resolve: {e}")
        return 1
    render.write_views(model.load(spec.root))
    print(f"resolved {', '.join(done)}")
    return 0


def cmd_propose(args) -> int:
    spec = _load(args)
    c = changes.current(spec)
    if c is None:
        print("spec propose: no change is open")
        return 1
    ids = list(dict.fromkeys(_expand(args.ids)))
    missing = [i for i in ids if i not in spec.items and i not in spec.elements]
    if missing:
        print(f"spec propose: unknown IDs: {', '.join(missing)}; nothing recorded")
        return 1
    try:
        changes.add_proposal(c, ids, args.why)
    except changes.ChangeError as e:
        print(f"spec propose: {e}")
        return 1
    render.write_views(model.load(spec.root))
    print(f"proposed for the engineer's explicit approval in {c.id}: {', '.join(ids)}")
    return 0


def cmd_friction(args) -> int:
    spec = _load(args)
    c = changes.current(spec)
    if c is None:
        print("spec friction: no change is open")
        return 1
    changes.log_friction(c, args.workaround, args.proposal)
    render.write_views(model.load(spec.root))
    print(f"logged in {c.id}; the engineer sees it in the change record")
    return 0


def _repo_root(start: Path) -> Path:
    for d in [start, *start.parents]:
        if (d / ".git").exists():
            return d
    return start


def cmd_init(args) -> int:
    repo = (Path(args.repo) if args.repo else _repo_root(Path.cwd())).resolve()
    harnesses = args.harness or init.installed_harnesses(repo) or ["claude-code"]  # a re-run refreshes them all
    try:
        steps = init.run(repo, harnesses, check_only=args.check, instructions=not args.no_instructions)
    except init.InitError as e:
        print(f"spec init: {e}")
        return 1
    if args.check:
        stale = [s for s in steps if s.status == "differs"]
        for s in stale:
            print(f"  {s.path}: {s.note}")
        print("spec init --check: " + (f"{len(stale)} files differ; run `spec init` to refresh them"
                                       if stale else "up to date"))
        return 1 if stale else 0
    print(f"spec init: {repo}")
    shown: dict[str, list[init.Step]] = {}
    for s in steps:  # a skill's files are reported as one line
        home = init.SKILL_COPY if s.path.startswith(init.SKILL_COPY + "/") else None
        shown.setdefault(home + "/" if home else s.path, []).append(s)
    for path, group in shown.items():
        changed = [s for s in group if s.status not in ("unchanged", "kept")]
        status = (changed[0].status if len({s.status for s in changed}) == 1 else "updated") if changed \
            else group[0].status
        note = group[0].note if len(group) == 1 else f"{len(group)} files"
        print(f"  {status:<9} {path}" + (f"  ({note})" if note else ""))
    print("\nCommit the files it wrote in the repository. The links in your home folder are this machine's.")
    if steps[0].status == "created":
        print("Next, ask your agent to onboard the project. The syseng skill tells it how.")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="spec", description="Systems-engineering spec toolkit")
    parser.add_argument("--spec", help="spec directory (default: find spec/ from here upward)")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("check", help="report everything unfinished in the spec")
    p.add_argument("--merge", action="store_true",
                   help="also list the alterations awaiting the engineer's answer (preparing a merge); never fails "
                        "because of them")
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
    p.add_argument("--via", default="terminal", choices=["terminal", "chat", "menu", "page", "restated"],
                   help="how the engineer gave it; `restated` when they restated what the item says")
    p.add_argument("--by", help="who approved (default: the repository's version-control user name)")
    p.add_argument("--note", help="anything else about how it was given, such as a pasted reply they confirmed")
    p.set_defaults(fn=cmd_approve)
    p = sub.add_parser("propose", help="propose items for the engineer's explicit approval, saying why")
    p.add_argument("ids", nargs="+", help="IDs, or ranges like CHECK-3..CHECK-5")
    p.add_argument("--why", required=True, help="why these deserve the engineer's attention")
    p.set_defaults(fn=cmd_propose)
    p = sub.add_parser("change", help="open, close or show the change record edits are logged in")
    p.add_argument("action", choices=["start", "close", "show"])
    p.add_argument("request", nargs="?", help="start: what the engineer asked for, summarized")
    p.add_argument("--mode", choices=list(changes.MODES), help="default: code-first")
    p.add_argument("--target", help="implementation the change targets (default: the primary one)")
    p.add_argument("--slug", help="a few words for the file name")
    p.set_defaults(fn=cmd_change)
    p = sub.add_parser("edit", help="change the spec with a YAML batch on stdin (see `spec edit --help`)",
                       description=edit.__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--dry-run", action="store_true", help="show context and validate, but write nothing")
    p.add_argument("--file", help="read the batch from a file instead of stdin")
    p.add_argument("--retry", action="store_true",
                   help="send again the last batch that needed acknowledgments or had errors")
    p.add_argument("--ack", action="append", metavar="ID=NOTE", help="acknowledge an affected item; repeat for each")
    p.set_defaults(fn=cmd_edit)
    p = sub.add_parser("status", help="what's open, what awaits the engineer, and the check summary")
    p.set_defaults(fn=cmd_status)
    p = sub.add_parser("decide", help="add an open decision (YAML on stdin: question, importance, involves, options)")
    p.add_argument("--file", help="read the decision from a file instead of stdin")
    p.set_defaults(fn=cmd_decide)
    p = sub.add_parser("resolve", help="record the engineer's choice on open decisions")
    p.add_argument("ids", nargs="+")
    p.add_argument("--words", required=True, help="the engineer's words, as evidence")
    p.add_argument("--option", type=int, help="the option number chosen (default: the recommended one)")
    p.set_defaults(fn=cmd_resolve)
    p = sub.add_parser("friction", help="report a workaround you needed, with a proposed improvement")
    p.add_argument("--workaround", required=True)
    p.add_argument("--proposal", required=True)
    p.set_defaults(fn=cmd_friction)
    p = sub.add_parser("init", help="set up a repository: spec skeleton, skill and harness glue",
                       description=init.__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--harness", action="append", choices=list(init.HARNESSES),
                   help="agent harness to set up for; repeat for several (default: the ones already set up, "
                        "else claude-code)")
    p.add_argument("--repo", help="repository to set up (default: the one containing the current directory)")
    p.add_argument("--check", action="store_true", help="report files that differ from a fresh setup; write nothing")
    p.add_argument("--no-instructions", action="store_true",
                   help="leave AGENTS.md and CLAUDE.md alone instead of adding the section that points sessions at the skill")
    p.set_defaults(fn=cmd_init)
    return parser


def commands() -> set[str]:
    sub = next(a for a in build_parser()._actions if isinstance(a, argparse._SubParsersAction))
    return set(sub.choices)


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    return args.fn(args)
