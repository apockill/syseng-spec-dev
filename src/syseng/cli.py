"""The `spec` command (CLI-1).

  spec check [--merge] [--todo] [--json]   report everything unfinished (CHECK-1)
  spec render                               write the review page (and remove old Markdown views)
  spec show ID                              one item: trace, children, verification, history
  spec lock ID... [--words TEXT] [--via]    record a person's lock, with who and how (SYS-33); alias: approve
  spec propose ID... --why TEXT             propose items for the engineer's explicit approval (SYS-38)
  spec change start|close|show              open and close the change record edits are logged in
  spec edit [--dry-run] < edits.yaml        change the spec (CLI-5 to CLI-8)
  spec decide < decision.yaml               add an open decision with options (CHANGE-10)
  spec resolve D1 ... --words TEXT          record the engineer's choice (CHANGE-12)
  spec issue [FILE] --title … [--send CODE] report a problem as an issue, with consent (SYS-56)
  spec init [--harness NAME]                set up a repository in one step (SYS-5)
  spec migrate [--dry-run]                  move the spec to the current format, after agents convert words
  spec diff [OLDER] [NEWER] [--since-review] [--format text|yaml]   what changed in the spec (SYS-48)
  spec review [--against REV] [--section NAME --format text|yaml]  the review page, or one section of it
  spec feedback apply|respond|list          apply a review page's feedback block; answer its comments

Run from anywhere inside a repository that has spec/toolkit.yaml, or pass --spec DIR.
"""

import argparse
import datetime
import json
import re
import sys
from pathlib import Path

from syseng import (changes, diff, edit, feedback, fingerprint, init, issue, levels, migrate, model, page, pagedata,
                    people, render, review, yamlio)
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
                      f"Keep it: `lock {alt['id']}`")
            print()
        print(checker.summarize(findings))
    return 1 if any(f.severity == "error" for f in findings) else 0


def cmd_render(args) -> int:
    """Removes Markdown views from before the review page, then writes the page (DR-60)."""
    spec = _load(args)
    for p in render.write_views(spec):
        print(f"removed {p.relative_to(spec.root.parent)}, a Markdown view the review page replaced")
    args.against, args.person, args.out, args.section, args.format = None, None, None, None, "text"
    return cmd_review(args)


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
    print(f"{iid} [{item.kind}, in {item.element}, level of intent: {levels.describe(spec, iid)}]")
    print(f"  {d.get('text') or d.get('title') or d.get('description', '')}")
    print(f"  attention: {review.describe(spec, iid)}")
    for a in review.history(spec, iid):
        said = " ".join(str(a.get("said") or a.get("words") or "").split())
        print(f"  locked {a.get('locked_at') or a.get('approved_at') or a.get('approved_on')} by "
              f"{a.get('by', 'the engineer')} via "
              f"{a.get('via')}" + (f": {said}" if said else ""))
    for r in levels.intent_records(d):  # SYS-39: what a person said about it, and when
        print(f"  {r.get('basis')} by {r.get('by')}, {r.get('when')}: {' '.join(str(r.get('said', '')).split())} "
              f"[{' '.join(str(r.get('context', '')).split())}]")
    if d.get("basis"):
        print(f"  basis: {d['basis']}")
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


def _settled(spec: model.Spec, iid: str) -> list[str]:
    """CLI-12: the resolved decisions that involved an item, so its approval shows what was discussed first."""
    return [f"{c.id} {d.get('id')}" for c in changes.all_changes(spec) for d in c.data.get("decisions") or []
            if d.get("status") == "resolved" and iid in (d.get("involves") or [])]


def cmd_approve(args) -> int:
    spec = _load(args)
    ids = list(dict.fromkeys(_expand(args.ids)))
    missing = [i for i in ids if i not in spec.items and i not in spec.elements]
    if missing:
        print(f"spec lock: unknown IDs: {', '.join(missing)}; nothing recorded")
        return 1
    now = datetime.datetime.now().astimezone().isoformat(timespec="minutes")
    by = args.by or people.person(spec.repo_root())[0]  # CLI-11
    records = list(spec.approvals)  # every approval is kept, oldest first (MODEL-35)
    for iid in ids:
        kind, data = review.kind_and_data(spec, iid)
        record = {"id": iid, "fingerprint": fingerprint.of(kind, data), "locked_at": now, "by": by,
                  "via": args.via, "batch": len(ids)}
        if args.words:  # a summary of what the person said; records made mechanically hold none (MODEL-34)
            record["said"] = args.words  # stored as `said`, the lock schema's field for it
        if args.note:
            record["note"] = args.note
        if _settled(spec, iid):
            record["after"] = _settled(spec, iid)
        record["text"] = fingerprint.summary(kind, data)
        records.append(record)
    records.sort(key=lambda a: (render._id_key(a["id"]), levels.when(a)))
    yamlio.write(spec.locks_path(), records)
    print(f"locked {len(ids)} item{'s' if len(ids) != 1 else ''}:")
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
            if args.full:  # the whole record as text: what an engineer would read, for an agent too (SYS-47)
                print(changes.view(spec, c), end="")
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
        print("\nThis edit affects locked or depended-on items. Nothing was written. Acknowledge each one by name")
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
    who, source = people.person(spec.repo_root())
    print(f"Recording people as: {who} (from {source})")
    if not people.is_set(spec.repo_root()):  # DR-56: on a machine where an agent commits, this is the agent
        print(f"  If that isn't the person directing this work, set it: "
              f"`git config {people.SETTING} \"Name <email>\"`")
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
            print(f"  {changes._label(spec, alt['id'])}, altered in {cid}. Keep it: `lock {alt['id']}`")
    waiting = [i for ch in changes.all_changes(spec) for p in ch.data.get("proposals") or [] for i in p.get("ids") or []
               if review.kind_and_data(spec, i) and levels.level_of(spec, i).level != levels.EXPLICIT]
    if waiting:
        print(f"Proposed for locking: `lock {', '.join(dict.fromkeys(waiting))}`")
    print(checker.summarize(checker.check(spec)))
    return 0


def cmd_decide(args) -> int:
    spec = _load(args)
    c = changes.current(spec)
    if c is None:
        print("spec decide: no change is open")
        return 1
    if args.withdraw:
        try:
            changes.withdraw(c, args.withdraw, args.reason or "")
        except changes.ChangeError as e:
            print(f"spec decide: {e}")
            return 1
        render.write_views(model.load(spec.root))
        print(f"withdrew open decision {args.withdraw} in {c.id}")
        return 0
    if args.dry_run:  # validate against a copy of the change, write nothing
        import copy
        probe = copy.copy(c)
        probe.data = copy.deepcopy(c.data)
        probe.save = lambda: None
        try:
            did = changes.add_decision(probe, _read_doc(args) or {}, replace=args.replace)
        except (changes.ChangeError, edit.EditError) as e:
            print(f"spec decide: {e}")
            return 1
        print(f"dry run: decision {did} is valid; nothing was written")
        return 0
    try:
        did = changes.add_decision(c, _read_doc(args) or {}, replace=args.replace)
    except (changes.ChangeError, edit.EditError) as e:
        print(f"spec decide: {e}")
        return 1
    render.write_views(model.load(spec.root))
    print(f"{'rewrote' if args.replace else 'added'} open decision {did} {'in' if args.replace else 'to'} {c.id}")
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
    print(f"proposed for locking in {c.id}: {', '.join(ids)}; the review page shows them with your reason")
    return 0


def cmd_issue(args) -> int:
    """CLI-29, CLI-33: a report goes out only with --send; without it, this shows what would go out."""
    if args.template:
        print(issue.TEMPLATE, end="")
        return 0
    if not args.file or not args.title:
        print("spec issue: give --template, or a report file and --title (start from `spec issue --template`)")
        return 1
    try:
        text = Path(args.file).read_text()
    except OSError as e:
        print(f"spec issue: can't read the report: {e}")
        return 1
    title, out = issue.full_title(args.title), issue.body(text, issue.toolkit_version())
    wrong = issue.problems(text)
    leaks = issue.leaks(f"{title}\n{out}", people.person(Path.cwd())[0], issue.remote_of(Path.cwd()))
    wrong += [f"it contains {leak}" for leak in leaks]
    if wrong:
        print("spec issue: nothing was sent. Rewrite the report in general terms:")
        print("\n".join(f"- {w}" for w in wrong))
        return 1
    shown = issue.code(title, out)
    if args.send != shown:
        if args.send:
            print("spec issue: nothing was sent: this isn't the text that code was shown for.\n")
        print(f"Would open an issue on the public repository {issue.REPOSITORY}. Show the engineer this exact text, "
              f"and add --send {shown} only once they agree:\n\nTitle: {title}\n\n{out}", end="")
        return 1 if args.send else 0
    try:
        print(f"sent: {issue.send(title, out)}")
    except RuntimeError as e:
        print(f"spec issue: nothing was sent: {e}. Give the engineer this text to file by hand:\n\n"
              f"Title: {title}\n\n{out}", end="")
        return 1
    return 0


def cmd_diff(args) -> int:
    """CLI-26: the spec differences between two versions, for agents (the review page renders the same data)."""
    spec = _load(args)
    try:
        if args.since_review:
            result = diff.since_review(spec, people.person(spec.repo_root())[0])
        else:
            result = diff.between(spec, args.older or "HEAD", args.newer)
    except diff.DiffError as e:
        print(f"spec diff: {e}")
        return 1
    if args.format == "yaml":
        print(yamlio.dumps(result.to_data()), end="")
    else:
        print(diff.to_text(result, spec), end="")
    return 0


def cmd_review(args) -> int:
    """CLI-25, CLI-24: the review page in one command, or any of its sections for an agent."""
    spec = _load(args)
    who = args.person or people.person(spec.repo_root())[0]
    data = pagedata.build(spec, who, args.against or [])
    if args.section:
        if args.format == "yaml":
            print(yamlio.dumps(data[args.section] if args.section != "items" else data["items"]), end="")
        else:
            print(pagedata.section_text(data, args.section), end="")
        return 0
    out = Path(args.out) if args.out else page.default_path(spec.root)
    page.write(data, out, out.parent / "reviews")
    awaiting = len(data["awaiting"]["decisions"]) + len(data["awaiting"]["alterations"])
    print(f"wrote {out}")
    print(f"  open it: file://{out.resolve()}")
    print(f"  {awaiting} awaiting a decision, {len(data['changes'][0]['items']) if data['changes'] else 0} items changed "
          f"since {data['changes'][0]['older']['label'] if data['changes'] else 'the last review'}, "
          f"{len(data['captured'])} intent records captured, {len(data['proposals'])} proposed for locking")
    return 0


def cmd_feedback(args) -> int:
    """CLI-23, CLI-27: apply the block a review page copied, in its person's name; answer each comment."""
    spec = _load(args)
    try:
        if args.action == "apply":
            text = Path(args.file).read_text() if args.file else sys.stdin.read()
            report = feedback.apply(spec, feedback.parse(text))
            for label, ids in (("locked", report.locked), ("unlocked", report.unlocked), ("kept", report.kept),
                               ("resolved", report.resolved), ("removed intent on", report.removed_intent)):
                if ids:
                    print(f"{label}: {', '.join(ids)}")
            if report.to_answer:
                print(f"to answer, with `spec feedback respond F<n> \"...\"`: {', '.join(report.to_answer)}")
            if report.already:
                print(f"already on record, skipped: {', '.join(report.already)}")
            for r in report.refused:
                print(f"not applied: {r}")
            if not any(vars(report).values()):
                print("reviewed, with nothing to add; recorded as their latest review")
        elif args.action == "respond":
            if len(args.rest) < 2:
                print('spec feedback respond: give the item and your response, as in `spec feedback respond F2 "..."`')
                return 1
            f = feedback.respond(spec, args.rest[0], " ".join(args.rest[1:]))
            print(f"responded to {f['n']}")
        else:
            waiting = feedback.unanswered(spec)
            for _, f in waiting:
                print(f"{f['n']} [{f.get('kind')}] {f.get('id') or f.get('decision') or 'general'}: {f.get('comment')}")
            print(f"{len(waiting)} waiting for a response" if waiting else "every feedback item has a response")
    except (feedback.FeedbackError, changes.ChangeError, edit.EditError) as e:
        print(f"spec feedback: {e}")
        return 1
    render.write_views(model.load(spec.root))
    return 0


def cmd_migrate(args) -> int:
    """CLI-28: the mechanical part of moving a spec to intent records and locks (DR-63)."""
    spec = _load(args)
    try:
        report = migrate.run(spec, changes.current(spec), dry_run=args.dry_run)
    except (migrate.MigrateError, changes.ChangeError) as e:
        print(f"spec migrate: {e}")
        return 1
    verb = "would" if args.dry_run else "did"
    print(f"spec migrate {'(dry run) ' if args.dry_run else ''}{verb}:")
    print(f"  carry {len(report['carried'])} locks over items this change only reworded"
          + (f": {', '.join(report['carried'])}" if report["carried"] else ""))
    print(f"  move {report['locks']} locks to locks.yaml, removing the words of {report['words_removed']}")
    print(f"  take verbatim words out of {report['scrubbed']} logged values and answers in the change records")
    print(f"  remove {len(report['legacy_records'])} hand-written change records from before records were YAML")
    print(f"  set spec_version 2; flow-down: {report['flow_down']}")
    if not args.dry_run:
        render.write_views(model.load(spec.root))
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
    if not people.is_set(repo):  # DR-56: intent and locks name a person, who may not be version control's user
        who, source = people.person(repo)
        print(f"Intent and locks will be recorded as {who} (from {source}). If that isn't you, set it once on this "
              f"machine: `git config --global {people.SETTING} \"Name <email>\"`.")
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
    p = sub.add_parser("render", help="write the review page, removing Markdown views from earlier versions")
    p.set_defaults(fn=cmd_render)
    p = sub.add_parser("show", help="show one item with its trace, level of intent and locks")
    p.add_argument("id")
    p.set_defaults(fn=cmd_show)
    p = sub.add_parser("lock", aliases=["approve"], help="record a person's lock on items (alias: approve)")
    p.add_argument("ids", nargs="+", help="IDs, or ranges like NEED-1..NEED-12")
    p.add_argument("--words", help="a summary of what the person said, never their exact words")
    p.add_argument("--via", default="terminal", choices=["terminal", "chat", "menu", "page"],
                   help="how the person gave it")
    p.add_argument("--by", help=f"who locked it, as Name <email> (default: `git config {people.SETTING}`, then "
                                f"${people.ENV}, then version control's user)")
    p.add_argument("--note", help="anything else about how it was given, such as a pasted reply they confirmed")
    p.set_defaults(fn=cmd_approve)
    p = sub.add_parser("propose", help="recommend items for the engineer to lock, saying why")
    p.add_argument("ids", nargs="+", help="IDs, or ranges like CHECK-3..CHECK-5")
    p.add_argument("--why", required=True, help="why these deserve the engineer's attention")
    p.set_defaults(fn=cmd_propose)
    p = sub.add_parser("change", help="open, close or show the change record edits are logged in")
    p.add_argument("action", choices=["start", "close", "show"])
    p.add_argument("request", nargs="?", help="start: what the engineer asked for, summarized")
    p.add_argument("--mode", choices=list(changes.MODES), help="default: code-first")
    p.add_argument("--target", help="implementation the change targets (default: the primary one)")
    p.add_argument("--slug", help="a few words for the file name")
    p.add_argument("--full", action="store_true", help="show: print the whole record as text")
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
    p.add_argument("--replace", metavar="D<n>", help="rewrite this open decision of the open change in place")
    p.add_argument("--withdraw", metavar="D<n>", help="withdraw this open decision, overtaken by events (needs --reason)")
    p.add_argument("--reason", help="why the decision is withdrawn")
    p.add_argument("--dry-run", action="store_true", help="check the decision without recording it")
    p.set_defaults(fn=cmd_decide)
    p = sub.add_parser("resolve", help="record the engineer's choice on open decisions")
    p.add_argument("ids", nargs="+")
    p.add_argument("--words", required=True, help="the engineer's words, as evidence")
    p.add_argument("--option", type=int, help="the option number chosen (default: the recommended one)")
    p.set_defaults(fn=cmd_resolve)
    p = sub.add_parser("issue", help="report a problem with the toolkit as an issue, with the engineer's consent",
                       description=issue.__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("file", nargs="?", help="the report, written from `spec issue --template`")
    p.add_argument("--title", help="a short title, free of anything specific to the project")
    p.add_argument("--template", action="store_true", help="print the report's template")
    p.add_argument("--send", metavar="CODE", help="send it, with the code the preview gave; only after the engineer agreed")
    p.set_defaults(fn=cmd_issue)
    p = sub.add_parser("diff", help="what changed in the spec between two versions (default: HEAD to the working tree)",
                       description=diff.__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("older", nargs="?", help="a branch (compared at its merge base), tag or commit; default HEAD")
    p.add_argument("newer", nargs="?", help="a branch, tag or commit; default the working tree")
    p.add_argument("--since-review", action="store_true", help="compare against your last review instead")
    p.add_argument("--format", choices=["text", "yaml"], default="text")
    p.set_defaults(fn=cmd_diff)
    p = sub.add_parser("review", help="generate the review page (or print one of its sections)",
                       description=pagedata.__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--against", action="append", metavar="REV",
                   help="also compare against this branch, tag or commit; repeat for several")
    p.add_argument("--person", help="who the page is for, as Name <email> (default: the person this machine records)")
    p.add_argument("--out", help="where to write the page (default: .syseng/review.html)")
    p.add_argument("--section", choices=list(pagedata.SECTIONS), help="print this section instead of writing the page")
    p.add_argument("--format", choices=["text", "yaml"], default="text")
    p.set_defaults(fn=cmd_review)
    p = sub.add_parser("feedback", help="apply a review page's feedback block (stdin or --file), or answer it",
                       description=feedback.__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("action", choices=["apply", "respond", "list"])
    p.add_argument("rest", nargs="*", help="respond: the item (F<n>) and your response")
    p.add_argument("--file", help="apply: read the block from a file instead of stdin")
    p.set_defaults(fn=cmd_feedback)
    p = sub.add_parser("migrate", help="move the spec to the current format (intent records and locks)",
                       description=migrate.__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--dry-run", action="store_true", help="report what it would do; write nothing")
    p.set_defaults(fn=cmd_migrate)
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
    try:
        return args.fn(args)
    except BrokenPipeError:  # the reader went away, as with `spec show X | head`: not an error
        import os
        os.dup2(os.open(os.devnull, os.O_WRONLY), sys.stdout.fileno())
        return 0
