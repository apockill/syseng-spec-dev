"""Editing through the CLI (CLI-5 to CLI-8), logged in change records (CHANGE)."""

import pytest

from syseng import changes, cli, edit, fingerprint, yamlio


@pytest.fixture
def open_spec(spec):
    """A spec with an open change, ready for edits."""
    spec.write()
    changes.start(spec.load(), "Make better widgets", None, None, "widgets")
    return spec


def _change(spec) -> dict:
    return changes.current(spec.load()).data


def _add_core(text="The core shall polish each widget.", **extra):
    return {"add": "requirement", "element": "CORE", "text": text, "traces_to": "SYS-1", "origin": "agent",
            "why": "polished widgets sell.", "reason": "the engineer asked for polish", **extra}


def test_edit_requires_an_open_change(spec):
    spec.write()
    with pytest.raises(edit.EditError, match="no change is open"):
        edit.run(spec.root, [_add_core()])


def test_every_operation_needs_a_reason(open_spec):
    op = _add_core()
    del op["reason"]
    with pytest.raises(edit.EditError, match="has no `reason`"):
        edit.run(open_spec.root, [op])
    with pytest.raises(edit.EditError, match="has no `reason`"):
        edit.run(open_spec.root, [{"remove": "CORE-1"}])


def test_add_allocates_the_next_unused_id(open_spec):
    yamlio.write(open_spec.root / "retired.yaml", [{"element": "CORE", "ids": ["CORE-2"], "note": "gone"}])
    result = edit.run(open_spec.root, [_add_core()])
    assert result.applied and result.ids == ["CORE-3"]   # skips the retired CORE-2
    assert "CORE-3" in open_spec.load().items


def test_edit_shows_context_before_and_after(open_spec):
    result = edit.run(open_spec.root, [{"modify": "CORE-1", "set": {"text": "The core shall stamp each widget twice."},
                                        "reason": "double stamps"}], dry_run=True)
    joined = "\n".join(result.context)
    assert "- text: The core shall stamp each widget." in joined
    assert "+ text: The core shall stamp each widget twice." in joined
    assert "refines SYS-1" in joined


def test_edit_touching_approved_item_needs_named_acks(open_spec):
    spec = open_spec.load()
    req = spec.items["CORE-1"]
    yamlio.write(open_spec.root / "approvals.yaml", [{"id": "CORE-1", "fingerprint": fingerprint.of_item(req)}])
    batch = {"edits": [{"modify": "CORE-1", "set": {"text": "The core shall stamp each widget twice."},
                        "reason": "double stamps"}]}
    result = edit.run(open_spec.root, batch)
    assert not result.applied
    assert set(result.needs_acks) == {"CORE-1", "CORE-V1"}   # approved itself; verified by CORE-V1
    assert open_spec.load().items["CORE-1"].data["text"] == "The core shall stamp each widget."
    batch["acks"] = {"CORE-1": "the engineer asked for double stamps", "CORE-V1": "test now checks two stamps"}
    assert edit.run(open_spec.root, batch).applied
    entry = _change(open_spec)["entries"][-1]
    assert entry["acks"]["CORE-V1"] == "test now checks two stamps"


def test_edit_without_impact_applies_immediately(open_spec):
    result = edit.run(open_spec.root, [_add_core()])
    assert result.applied and not result.needs_acks


def test_edit_that_introduces_errors_is_rejected_and_writes_nothing(open_spec):
    result = edit.run(open_spec.root, [_add_core(text="The core shall polish widgets where possible.")])
    assert not result.applied
    assert [f.code for f in result.errors] == ["W003"]
    assert str(result.errors[0].file).startswith(str(open_spec.root))   # real path, not the scratch copy
    assert "CORE-2" not in open_spec.load().items
    assert _change(open_spec)["entries"] == []


def test_preexisting_errors_do_not_block_unrelated_edits(open_spec):
    open_spec.files["elements/CORE/element.yaml"]["depends_on"] = ["GHOST"]   # an existing S006
    open_spec.write()
    assert edit.run(open_spec.root, [_add_core()]).applied


def test_multiple_operations_in_one_batch(open_spec):
    batch = [_add_core(), _add_core(text="The core shall box each widget.", why="boxes protect widgets.")]
    result = edit.run(open_spec.root, batch)
    assert result.applied and result.ids == ["CORE-2", "CORE-3"]


def test_remove_retires_the_id_and_drops_its_approval(open_spec):
    edit.run(open_spec.root, [_add_core()])
    spec = open_spec.load()
    yamlio.write(open_spec.root / "approvals.yaml", [{"id": "CORE-2", "fingerprint": fingerprint.of_item(spec.items["CORE-2"])}])
    result = edit.run(open_spec.root, {"edits": [{"remove": "CORE-2", "reason": "polish was dropped"}],
                                       "acks": {"CORE-2": "the engineer dropped polish"}})
    assert result.applied
    spec = open_spec.load()
    assert "CORE-2" not in spec.items and "CORE-2" in spec.retired_ids()
    assert spec.approval_for("CORE-2") is None
    with pytest.raises(edit.EditError, match="retired"):
        edit.run(open_spec.root, [_add_core(id="CORE-2")])


def test_removing_a_referenced_item_is_rejected(open_spec):
    result = edit.run(open_spec.root, {"edits": [{"remove": "CORE-1", "reason": "no more stamps"}],
                                       "acks": {"CORE-V1": "will go too"}})
    assert not result.applied
    assert "T003" in [f.code for f in result.errors]   # CORE-V1 would verify nothing


def test_dry_run_writes_nothing(open_spec):
    result = edit.run(open_spec.root, [_add_core()], dry_run=True)
    assert not result.applied and not result.errors
    assert "CORE-2" not in open_spec.load().items


def test_unknown_field_suggests_close_match(open_spec):
    op = _add_core()
    op["txt"] = op.pop("text")
    with pytest.raises(edit.EditError, match="Did you mean `text`"):
        edit.run(open_spec.root, [op])


def test_edits_are_logged_with_reasons_in_the_change_record(open_spec):
    edit.run(open_spec.root, {"edits": [{"modify": "CORE-1", "set": {"text": "The core shall stamp each widget twice."},
                                         "reason": "double stamps"}],
                              "acks": {"CORE-V1": "the test now checks two stamps"}})
    entry = _change(open_spec)["entries"][-1]
    assert entry["op"] == "modify" and entry["id"] == "CORE-1" and entry["reason"] == "double stamps"
    assert entry["before"]["text"] == "The core shall stamp each widget."
    assert entry["after"]["text"] == "The core shall stamp each widget twice."
    view = (open_spec.root / "changes").glob("*.md")
    assert any("double stamps" in p.read_text() for p in view)


def test_change_defaults_to_code_first_and_the_primary_target(open_spec):
    data = _change(open_spec)
    assert data["mode"] == "code-first" and data["target"] == "python"
    assert data["request"] == "Make better widgets"


def test_spec_first_mode_is_recorded(spec):
    spec.write()
    c = changes.start(spec.load(), "Plan the gizmo", "spec-first", None, None)
    assert c.data["mode"] == "spec-first"


def test_only_one_change_is_open_at_a_time(open_spec):
    with pytest.raises(changes.ChangeError, match="still open"):
        changes.start(open_spec.load(), "Another thing", None, None, None)


def test_cli_exit_code_two_means_acks_needed(open_spec, monkeypatch, capsys):
    spec = open_spec.load()
    yamlio.write(open_spec.root / "approvals.yaml",
                 [{"id": "CORE-1", "fingerprint": fingerprint.of_item(spec.items["CORE-1"])}])
    batch = tmp = open_spec.root.parent / "batch.yaml"
    yamlio.write(tmp, [{"modify": "CORE-1", "set": {"text": "The core shall stamp each widget twice."},
                        "reason": "double stamps"}])
    assert cli.main(["--spec", str(open_spec.root), "edit", "--file", str(batch)]) == 2
    out = capsys.readouterr().out
    assert "acks:" in out and 'CORE-1: "<note>"' in out and "CORE-V1" in out


def test_rationale_only_change_needs_no_acks(open_spec):
    result = edit.run(open_spec.root, [{"modify": "CORE-1", "set": {"why": "stamps prove origin."},
                                        "reason": "a clearer rationale"}])
    assert result.applied and not result.needs_acks   # meaning unchanged, so CORE-V1 isn't affected


def test_show_prints_the_history_of_logged_changes(open_spec, capsys):
    edit.run(open_spec.root, [{"modify": "CORE-1", "set": {"why": "stamps prove origin."},
                               "reason": "a clearer rationale"}])
    cli.main(["--spec", str(open_spec.root), "show", "CORE-1"])
    out = capsys.readouterr().out
    assert "history: modify in" in out and "a clearer rationale" in out


def test_test_link_changes_are_logged_and_shown(open_spec):
    result = edit.run(open_spec.root, [{"modify": "CORE-V1", "set": {"tests": {"python": ["tests/test_core.py::test_other"]}},
                                        "reason": "the old test was renamed"}])
    assert result.applied and not result.needs_acks           # links aren't meaning (MODEL-31)
    assert any("+ tests:" in line for line in result.context)
    entry = _change(open_spec)["entries"][-1]
    assert entry["before"]["tests"] == {"python": ["tests/test_core.py::test_stamp"]}
    assert entry["after"]["tests"] == {"python": ["tests/test_core.py::test_other"]}
