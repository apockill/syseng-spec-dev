"""Levels of intent, intent records, who records them, flow-down and conflicts (SYS-42 to SYS-50; DR-54 to DR-62)."""

import pytest

from syseng import changes, check, cli, edit, levels, model, people, yamlio


def _approve(spec, root, *ids):
    assert cli.main(["--spec", str(root), "approve", *ids, "--by", "Ada <ada@example.com>"]) == 0
    spec.files["approvals.yaml"] = yamlio.read(root / "approvals.yaml")


def _start(root, mode=None):
    changes.start(model.load(root), "widgets", mode, None, None)


def _intent(said="wants each widget stamped", basis="stated"):
    return {"basis": basis, "context": "Planning the widget line.", "said": said}


# ---------------------------------------------------------------- levels (SYS-42, CHECK-18, MODEL-40)
def test_each_item_gets_the_level_its_records_give_it(spec):
    root = spec.write()
    s = model.load(root)
    assert levels.level_of(s, "NEED-1").level == levels.STATED      # needs come from people
    assert levels.level_of(s, "SYS-1").level == levels.STATED       # the engineer's words, read from older fields
    core = levels.level_of(s, "CORE-1")                             # an agent's requirement under it
    assert (core.level, core.under) == (levels.DERIVED, "SYS-1")
    assert levels.level_of(s, "CORE-V1").level == levels.DERIVED    # verification items count as derived
    assert levels.level_of(s, "CORE").level == levels.DERIVED       # and so do element definitions
    _approve(spec, root, "CORE-1")
    assert levels.level_of(model.load(root), "CORE-1").level == levels.EXPLICIT


def test_the_highest_level_applies(spec):
    root = spec.write()
    _start(root)
    assert edit.run(root, {"edits": [{"modify": "CORE-1", "intent": _intent(basis="guided"),
                                      "reason": "the engineer chose stamping"}]}).applied
    assert levels.level_of(model.load(root), "CORE-1").level == levels.GUIDED
    _approve(spec, root, "CORE-1")
    assert levels.level_of(model.load(root), "CORE-1").level == levels.EXPLICIT


def test_an_added_item_and_what_derives_from_it_count_as_added(spec):
    spec.files["elements/CORE/requirements.yaml"][0].update(basis="added")
    root = spec.write()
    s = model.load(root)
    assert levels.level_of(s, "CORE-1").level == levels.ADDED
    assert (levels.level_of(s, "CORE-V1").level, levels.level_of(s, "CORE-V1").under) == (levels.ADDED, "SYS-1")


def test_an_invalid_basis_is_reported(spec):
    spec.files["elements/CORE/requirements.yaml"][0].update(basis="important")
    spec.write()
    assert "A008" in spec.codes()


# ---------------------------------------------------------------- changed since (CHECK-19, CHECK-24)
def test_a_change_after_a_lock_is_a_to_do_until_answered(spec):
    root = spec.write()
    _approve(spec, root, "CORE-1")
    spec.files["elements/CORE/requirements.yaml"][0]["text"] = "The core shall stamp each widget twice."
    spec.write()
    s = spec.load()
    lv = levels.level_of(s, "CORE-1")
    assert (lv.level, lv.given, lv.changed) == (levels.STATED, levels.EXPLICIT, True)   # decays one step (CHECK-28)
    assert levels.label(lv) == "locked to an earlier version"
    assert any(f.code == "A003" and f.item == "CORE-1" and "changed since Ada" in f.message for f in check.check(s))
    _approve(spec, root, "CORE-1")                                    # kept: a newer lock matches
    assert not levels.level_of(model.load(root), "CORE-1").changed


def test_changed_is_judged_against_the_newest_record(spec):
    root = spec.write()
    _start(root)
    assert edit.run(root, {"edits": [{"modify": "CORE-1", "intent": _intent(), "reason": "asked for"}]}).applied
    batch = {"edits": [{"modify": "CORE-1", "set": {"text": "The core shall stamp each widget twice."},
                        "reason": "double stamps", "intent": _intent("wants two stamps")}]}
    result = edit.run(root, batch)
    if result.needs_acks:
        result = edit.run(root, {**batch, "acks": {k: "fine" for k in result.needs_acks}})
    assert result.applied
    assert not levels.level_of(model.load(root), "CORE-1").changed   # the older record is superseded


# ---------------------------------------------------------------- intent records (MODEL-36, MODEL-37, CHECK-20, CHECK-25)
def test_intent_added_through_an_edit_is_filled_in(spec, monkeypatch):
    monkeypatch.setenv("SYSENG_AUTHOR", "Grace <grace@example.com>")
    root = spec.write()
    _start(root)
    assert edit.run(root, {"edits": [{"modify": "CORE-1", "intent": _intent(), "reason": "asked for"}]}).applied
    s = model.load(root)
    rec = s.items["CORE-1"].data["intent"][0]
    assert rec["by"] == "Grace <grace@example.com>" and rec["when"] and rec["fingerprint"]
    assert rec["fingerprint"] == levels.review.current_fingerprint(s, "CORE-1")
    assert levels.level_of(s, "CORE-1").level == levels.STATED
    assert not [f for f in check.check(s) if f.severity == "error"]


def test_an_intent_record_needs_every_field(spec):
    spec.files["elements/CORE/requirements.yaml"][0]["intent"] = [{"by": "Ada", "said": "stamp them", "basis": "stated"}]
    spec.write()
    msgs = [f.message for f in spec.findings() if f.code == "A006"]
    assert msgs and "`context` is missing" in msgs[0] and "`fingerprint` is missing" in msgs[0]
    assert "`by` must be a person as `Name <email>`" in msgs[0]


def test_an_intent_record_never_quotes(spec):
    spec.files["elements/CORE/requirements.yaml"][0]["intent"] = [{
        "by": "Ada", "when": "2026-10-21 10:00", "context": "Planning.", "basis": "stated", "fingerprint": "x",
        "said": 'said "stamp every widget"'}]
    spec.write()
    assert "A007" in spec.codes()
    spec.files["elements/CORE/requirements.yaml"][0]["intent"][0]["said"] = "wants every widget's 'stamp' visible"
    spec.write()
    assert "A007" not in spec.codes()                                 # single quotes and apostrophes are fine


def test_an_edit_refuses_an_intent_record_without_a_basis(spec):
    root = spec.write()
    _start(root)
    with pytest.raises(edit.EditError, match="basis"):
        edit.run(root, {"edits": [{"modify": "CORE-1", "intent": {"context": "x", "said": "y"}, "reason": "r"}]})


# ---------------------------------------------------------------- who (SYS-43, CLI-11, DR-56)
def test_the_person_comes_from_the_toolkit_setting_first(tmp_path, monkeypatch):
    answers = {"syseng.author": "Ada <ada@example.com>", "user.name": "agent-bot", "user.email": "bot@example.com"}
    monkeypatch.setattr(people, "_git", lambda repo, key: answers.get(key, ""))
    assert people.person(tmp_path) == ("Ada <ada@example.com>", "git config syseng.author")
    answers["syseng.author"] = ""
    monkeypatch.setenv("SYSENG_AUTHOR", "Grace <grace@example.com>")
    assert people.person(tmp_path)[0] == "Grace <grace@example.com>"
    monkeypatch.delenv("SYSENG_AUTHOR")
    assert people.person(tmp_path)[0] == "agent-bot <bot@example.com>"
    assert not people.is_set(tmp_path)


def test_an_approval_needs_no_words(spec, monkeypatch):
    monkeypatch.setenv("SYSENG_AUTHOR", "Ada <ada@example.com>")
    root = spec.write()
    assert cli.main(["--spec", str(root), "approve", "CORE-1", "--via", "chat"]) == 0
    record = yamlio.read(root / "approvals.yaml")[0]
    assert record["by"] == "Ada <ada@example.com>" and "words" not in record


# ---------------------------------------------------------------- flow-down (SYS-50, CHECK-22)
def _sub(spec, traces_to):
    spec.files["elements/SUB/element.yaml"] = {"id": "SUB", "title": "Stamper", "parent": "CORE", "depends_on": [],
                                               "purpose": "Stamps widgets."}
    spec.files["elements/SUB/requirements.yaml"] = [{"id": "SUB-1", "text": "The stamper shall ink each stamp.",
                                                     "origin": "agent", "traces_to": traces_to, "why": "ink shows."}]


def test_a_requirement_refines_one_of_its_parent_elements_requirements(spec):
    _sub(spec, "SYS-1")
    spec.write()
    assert "T005" in spec.codes(severity="todo")
    spec.files["toolkit.yaml"]["flow_down"] = "enforced"
    spec.write()
    assert "T005" in spec.codes()
    _sub(spec, "CORE-1")
    spec.write()
    assert "T005" not in spec.codes() + spec.codes(severity="todo")


# ---------------------------------------------------------------- conflicts (SYS-49, CLI-22, CHECK-26)
_REWORD = {"modify": "SYS-1", "set": {"text": "The system shall make blue widgets."}, "reason": "blue sells"}


def _edit(root, op, **extra):
    batch = {"edits": [{**op, **extra}]}
    result = edit.run(root, batch)
    if result.needs_acks:
        result = edit.run(root, {**batch, "acks": {k: "fine" for k in result.needs_acks}})
    return result


def test_spec_first_refuses_to_change_what_a_person_stated(spec):
    root = spec.write()
    _start(root, "spec-first")
    with pytest.raises(edit.EditError, match="raise the conflict|Raise the conflict"):
        _edit(root, _REWORD)


def test_spec_first_allows_a_rewording_or_the_persons_own_request(spec):
    root = spec.write()
    _start(root, "spec-first")
    assert _edit(root, _REWORD, rewording=True).applied
    assert _edit(root, {**_REWORD, "set": {"text": "The system shall make red widgets."}},
                 intent=_intent("asked for red widgets")).applied


def test_spec_first_allows_a_change_under_a_resolved_conflict_that_names_the_item(spec):
    root = spec.write()
    _start(root, "spec-first")
    c = changes.current(model.load(root))
    did = changes.add_decision(c, {"kind": "conflict", "question": "Blue or plain?", "importance": "colour",
                                   "involves": ["SYS-1"], "options": [{"label": "blue", "recommended": True},
                                                                       {"label": "plain"}]})
    with pytest.raises(edit.EditError):
        _edit(root, _REWORD, conflict=did)                            # not resolved yet
    changes.resolve(changes.current(model.load(root)), [did], "Ada chose blue (summary)", None)
    assert _edit(root, _REWORD, conflict=did).applied


def test_code_first_goes_ahead_and_the_done_check_asks_for_the_conflict(spec):
    root = spec.write()
    _start(root)
    assert _edit(root, _REWORD).applied
    assert "C001" in spec.codes()
    c = changes.current(model.load(root))
    changes.add_decision(c, {"kind": "conflict", "question": "Keep blue widgets?", "importance": "colour",
                             "involves": ["SYS-1"], "options": [{"label": "keep", "recommended": True},
                                                                 {"label": "roll back"}]})
    assert "C001" not in spec.codes()


def test_a_conflict_names_what_it_involves(spec):
    root = spec.write()
    _start(root)
    with pytest.raises(changes.ChangeError, match="involves"):
        changes.add_decision(changes.current(model.load(root)), {
            "kind": "conflict", "question": "q", "importance": "i",
            "options": [{"label": "a", "recommended": True}, {"label": "b"}]})


# ---------------------------------------------------------------- the agent's own drafts aren't alterations
def test_editing_an_item_added_earlier_in_the_same_change_alters_nothing_a_person_gave(spec):
    root = spec.write()
    _start(root)
    assert edit.run(root, {"edits": [{"add": "requirement", "element": "CORE", "id": "CORE-2", "origin": "engineer",
                                      "text": "The core shall count each widget.", "traces_to": "SYS-1",
                                      "source": "Ada (summary): count them", "reason": "asked"}]}).applied
    result = edit.run(root, {"edits": [{"modify": "CORE-2", "set": {"text": "The core shall count each stamp."},
                                        "reason": "stamps, not widgets"}]})
    assert result.applied and not result.needs_acks
    entry = changes.current(model.load(root)).data["entries"][-1]
    assert "raised" not in entry


def test_an_element_gaining_a_dependency_needs_no_acknowledgments(spec):
    spec.files["elements/SYS/decisions.yaml"] = [{
        "id": "DR-1", "title": "Stamp in the core", "decided_by": "engineer", "elements": ["SYS", "CORE"],
        "requirements": "CORE-1", "context": "c", "decision": "d"}]
    spec.files["elements/INK/element.yaml"] = {"id": "INK", "title": "Ink", "parent": "SYS", "depends_on": [],
                                               "purpose": "Supplies ink."}
    root = spec.write()
    _approve(spec, root, "CORE")
    _start(root)
    result = edit.run(root, {"edits": [{"modify": "CORE", "set": {"depends_on": ["INK"]}, "reason": "ink"}]})
    assert result.applied and not result.needs_acks


def test_new_repositories_enforce_flow_down(tmp_path):
    from syseng import init
    init._skeleton(tmp_path)
    assert yamlio.read(tmp_path / "spec" / "toolkit.yaml")["flow_down"] == "enforced"


def test_a_change_the_person_has_seen_on_a_review_stops_asking_but_stays_decayed(spec):
    root = spec.write()
    _approve(spec, root, "CORE-1")
    _start(root)
    assert _edit(root, {"modify": "CORE-1", "set": {"text": "The core shall stamp each widget twice."}, "reason": "twice"}).applied
    s = model.load(root)
    assert "A003" in [f.code for f in check.check(s) if f.item == "CORE-1"]
    assert [a["id"] for _, a in levels.review.unanswered(s)] == ["CORE-1"]
    yamlio.write(root / "reviews.yaml", [{"review": "r1", "by": "Ada <ada@example.com>", "at": "2999-01-01T00:00-07:00",
                                          "generated": "2999-01-01T00:00-07:00", "revision": "x", "dirty": False}])
    s = model.load(root)
    assert "A003" not in [f.code for f in check.check(s) if f.item == "CORE-1"]   # DR-68: seen, so it stops asking
    assert levels.review.unanswered(s) == []
    assert levels.level_of(s, "CORE-1").given == levels.EXPLICIT                 # and stays locked to an earlier version
