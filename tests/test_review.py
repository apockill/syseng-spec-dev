"""Review state, delegation and the facts agents weigh before a change (SYS-33 to SYS-40; DR-44)."""

import datetime

from syseng import changes, check, cli, edit, model, review, yamlio


def _approve(spec, root, *args):
    assert cli.main(["--spec", str(root), "approve", *args, "--by", "Ada"]) == 0
    spec.files["approvals.yaml"] = yamlio.read(root / "approvals.yaml")  # keep them through later writes


def _restamp(root, acks=None):
    batch = {"edits": [{"modify": "CORE-1", "set": {"text": "The core shall stamp each widget twice."},
                        "reason": "double stamps"}]}
    if acks:
        batch["acks"] = acks
    return edit.run(root, batch)


def test_items_under_an_approved_item_are_delegated(spec):
    root = spec.write()
    _approve(spec, root, "SYS-1", "--words", "approve SYS-1")
    s = spec.load()
    assert review.state_of(s, "SYS-1").state == review.APPROVED
    core, vi = review.state_of(s, "CORE-1"), review.state_of(s, "CORE-V1")
    assert (core.state, core.under, core.levels) == (review.DELEGATED, "SYS-1", 1)
    assert (vi.state, vi.under, vi.levels) == (review.DELEGATED, "SYS-1", 2)
    assert review.state_of(s, "NEED-1").state == review.UNREVIEWED
    unreviewed = {f.item for f in check.check(s) if f.code == "A003"}
    assert "NEED-1" in unreviewed and not unreviewed & {"CORE-1", "CORE-V1"}


def test_a_changed_item_is_neither_approved_nor_delegated(spec):
    root = spec.write()
    _approve(spec, root, "SYS-1", "CORE-1", "--words", "approve SYS-1, CORE-1")
    spec.files["elements/CORE/requirements.yaml"][0]["text"] = "The core shall stamp each widget twice."
    spec.write()
    s = spec.load()
    assert review.state_of(s, "CORE-1").state == review.CHANGED
    assert any(f.code == "A003" and f.item == "CORE-1" and "changed since" in f.message for f in check.check(s))


def test_every_approval_is_kept_with_who_and_how(spec, capsys):
    root = spec.write()
    _approve(spec, root, "CORE-1", "SYS-1", "--words", "approve CORE-1, SYS-1", "--via", "chat")
    _approve(spec, root, "CORE-1", "--words", "that's what I want", "--via", "restated", "--note", "said again")
    records = [a for a in yamlio.read(root / "approvals.yaml") if a["id"] == "CORE-1"]
    assert [(a["via"], a["batch"], a["by"]) for a in records] == [("chat", 2, "Ada"), ("restated", 1, "Ada")]
    assert records[0]["approved_at"].startswith(datetime.date.today().isoformat())
    assert records[1]["note"] == "said again"
    cli.main(["--spec", str(root), "show", "CORE-1"])
    out = capsys.readouterr().out
    assert "2 approvals in all" in out and "via restated" in out


def test_an_approval_lists_the_decisions_settled_before_it(spec):
    root = spec.write()
    c = changes.start(spec.load(), "widgets", None, None, None)
    changes.add_decision(c, {"question": "Stamp how?", "importance": "it shapes CORE-1", "involves": ["CORE-1"],
                             "options": [{"label": "ink", "recommended": True}, {"label": "laser"}]})
    changes.resolve(c, ["D1"], "ink, please", None)
    _approve(spec, root, "CORE-1", "--words", "CORE-1 LGTM")
    assert yamlio.read(root / "approvals.yaml")[0]["after"] == [f"{c.id} D1"]


def test_an_edit_shows_what_the_agent_should_weigh(spec):
    root = spec.write()
    _approve(spec, root, "SYS-1", "--words", "approve SYS-1")
    changes.start(spec.load(), "widgets", None, None, None)
    result = edit.run(root, {"edits": [{"modify": "CORE-1", "set": {"why": "stamps sell."}, "reason": "clearer"}]},
                      dry_run=True)
    assert any("attention: delegated under SYS-1" in line for line in result.context)


def _worded_core(spec):
    core = spec.files["elements/CORE/requirements.yaml"][0]
    core.update({"origin": "engineer", "source": '"stamp every widget"'})
    root = spec.write()
    changes.start(spec.load(), "restamp", None, None, None)
    return root


def test_altering_the_engineers_words_is_raised_until_kept(spec):
    root = _worded_core(spec)
    first = _restamp(root)
    assert "CORE-1" in first.needs_acks                          # the agent hears about it before it lands
    assert _restamp(root, {k: "fine" for k in first.needs_acks}).applied
    s = model.load(root)
    view = changes.view(s, changes.current(s))
    assert "## Alterations awaiting your answer" in view and "`CORE-1 LGTM`" in view
    assert any(f.code == "A004" and f.item == "CORE-1" for f in check.check(s))
    _approve(spec, root, "CORE-1", "--words", "CORE-1 LGTM")
    s = model.load(root)
    assert not [f for f in check.check(s) if f.code == "A004"]
    assert "CORE-1 (kept)" in changes.view(s, changes.current(s))


def test_rolling_back_an_alteration_answers_it(spec):
    root = _worded_core(spec)
    acks = {k: "fine" for k in _restamp(root).needs_acks}
    assert _restamp(root, acks).applied
    back = {"edits": [{"modify": "CORE-1", "set": {"text": "The core shall stamp each widget."}, "reason": "rolled back"}],
            "acks": acks}
    assert edit.run(root, back).applied
    s = model.load(root)
    assert not [f for f in check.check(s) if f.code == "A004"]
    assert "CORE-1 (rolled back)" in changes.view(s, changes.current(s))


def test_proposals_are_listed_with_reasons_until_approved(spec):
    root = spec.write()
    changes.start(spec.load(), "widgets", None, None, None)
    assert cli.main(["--spec", str(root), "propose", "CORE-1", "--why", "it decides how every widget looks"]) == 0
    s = model.load(root)
    view = changes.view(s, changes.current(s))
    assert "## Proposed for your explicit approval" in view and "`approve CORE-1`" in view
    assert "> The core shall stamp each widget." in view                     # its full text, on the spot
    assert "*Under:* SYS-1 (The system shall make widgets.)" in view        # and what it sits under
    _approve(spec, root, "CORE-1", "--words", "approve CORE-1")
    s = model.load(root)
    assert "*Already approved:* CORE-1" in changes.view(s, changes.current(s))


def test_a_proposed_decision_shows_its_reasoning_and_what_it_mentions(spec):
    spec.files["elements/CORE/decisions.yaml"] = [{
        "id": "DR-1", "title": "Stamp with ink", "decided_by": "agent", "elements": ["CORE"], "requirements": "CORE-1",
        "context": "Stamps must last.", "decision": "Ink, because CORE-1 needs every widget stamped.",
        "alternatives": "Lasers, which SYS-1 can't afford.", "consequences": "Ink costs money."}]
    root = spec.write()
    changes.start(spec.load(), "widgets", None, None, None)
    assert cli.main(["--spec", str(root), "propose", "DR-1", "--why", "it decides how widgets look"]) == 0
    s = model.load(root)
    view = changes.view(s, changes.current(s))
    assert "### DR-1: Stamp with ink" in view
    assert "*Alternatives:* Lasers, which SYS-1 can't afford." in view
    assert "  - CORE-1: The core shall stamp each widget." in view               # what it decides, in full
    assert "*Mentioned:* SYS-1 (The system shall make widgets.)" in view


def test_a_proposal_needs_a_reason(spec):
    root = spec.write()
    changes.start(spec.load(), "widgets", None, None, None)
    assert cli.main(["--spec", str(root), "propose", "CORE-1", "--why", " "]) == 1


def test_quotes_need_words_a_date_and_context(spec):
    spec.files["elements/CORE/requirements.yaml"][0]["quotes"] = [{"words": "stamp them all", "said": "2026-10-17 09:30"}]
    spec.write()
    assert any(f.code == "S007" and "context" in f.message for f in spec.findings())


def test_quotes_are_shown_with_when_and_what_was_discussed(spec):
    spec.files["elements/CORE/requirements.yaml"][0]["quotes"] = [
        {"words": "stamp them all", "said": "2026-10-17 09:30", "context": "talking about widget branding"}]
    root = spec.write()
    text = (root / "requirements.md").read_text()
    assert '"stamp them all"' in text and "2026-10-17 09:30" in text and "talking about widget branding" in text


def test_views_mark_approved_changed_and_delegated_items(spec):
    root = spec.write()
    _approve(spec, root, "SYS-1", "CORE-1", "--words", "approve SYS-1, CORE-1")
    reqs = spec.files["elements/CORE/requirements.yaml"]
    reqs[0]["text"] = "The core shall stamp each widget twice."
    reqs.append({"id": "CORE-2", "text": "The core shall count each widget.", "origin": "agent",
                 "traces_to": "SYS-1", "why": "inventory."})
    root = spec.write()
    text = (root / "requirements.md").read_text()
    assert "🔒 **SYS-1**" in text and "🔓 **CORE-1**" in text and "⤷SYS-1 **CORE-2**" in text


def test_no_importance_score_is_stored():
    for fields in edit.FIELDS.values():
        assert not fields & {"importance", "priority", "score", "criticality"}


def test_the_approver_defaults_to_the_version_control_user(spec, tmp_path, monkeypatch):
    monkeypatch.setattr(cli.subprocess, "run", lambda *a, **k: cli.subprocess.CompletedProcess(a, 0, "Grace\n", ""))
    assert cli._approver(tmp_path) == "Grace"


def test_each_logged_edit_records_when_it_happened(spec):
    root = spec.write()
    changes.start(spec.load(), "widgets", None, None, None)
    assert edit.run(root, {"edits": [{"modify": "CORE-1", "set": {"why": "stamps sell."}, "reason": "clearer"}]}).applied
    entry = changes.current(model.load(root)).data["entries"][0]
    assert entry["at"].startswith(datetime.date.today().isoformat())
