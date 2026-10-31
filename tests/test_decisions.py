"""Open decisions (CHANGE-3, CHANGE-10 to CHANGE-12) and the change record view (REVIEW-10, REVIEW-12)."""

import pytest

from syseng import changes, edit


@pytest.fixture
def change(spec):
    spec.write()
    return changes.start(spec.load(), "Make better widgets", None, None, None)


def _decision(**over):
    d = {"question": "Stamp twice or once?", "importance": "changes CORE-1's meaning",
         "involves": ["CORE-1"],
         "options": [{"label": "Twice", "recommended": True, "detail": "stronger proof"},
                     {"label": "Once", "detail": "cheaper"}]}
    d.update(over)
    return d


def test_decision_needs_options_with_exactly_one_recommended(change):
    with pytest.raises(changes.ChangeError, match="at least two"):
        changes.add_decision(change, _decision(options=[{"label": "Only", "recommended": True}]))
    with pytest.raises(changes.ChangeError, match="exactly one option"):
        changes.add_decision(change, _decision(options=[{"label": "A"}, {"label": "B"}]))


def test_decision_says_why_it_ranks_where_it_does(change):
    with pytest.raises(changes.ChangeError, match="importance"):
        changes.add_decision(change, _decision(importance=""))


def test_resolve_takes_the_recommended_options_for_a_set(change):
    d1 = changes.add_decision(change, _decision())
    d2 = changes.add_decision(change, _decision(question="Paint red or blue?",
                                                options=[{"label": "Red"}, {"label": "Blue", "recommended": True}]))
    changes.resolve(change, [d1, d2], "go with your recommendations", None)
    chosen = {d["id"]: d["chosen"] for d in change.data["decisions"]}
    assert chosen == {d1: "Twice", d2: "Blue"}
    assert all(d["words"] == "go with your recommendations" for d in change.data["decisions"])


def test_resolve_a_specific_option(change):
    d1 = changes.add_decision(change, _decision())
    changes.resolve(change, [d1], "once is enough", 2)
    assert change.data["decisions"][0]["chosen"] == "Once"


def test_view_puts_open_decisions_first_and_flags_the_engineers_items(spec, change):
    edit.run(spec.root, [{"add": "requirement", "element": "CORE", "text": "The core shall polish each widget.",
                          "traces_to": "SYS-1", "origin": "agent", "why": "shine.", "reason": "asked for polish"}])
    changes.add_decision(change, _decision(involves=["SYS-1"]))   # SYS-1 is the engineer's own words
    text = changes.view(spec.load(), changes.current(spec.load()))
    assert text.index("## Open decisions") < text.index("## Changes to the spec")
    assert "⚠" in text and "SYS-1" in text                          # CHANGE-11
    assert "**(recommended)**" in text
    assert "spec resolve D1" in text                                 # one statement accepts the set


def test_view_shows_the_reason_beside_each_change(spec, change):
    edit.run(spec.root, {"edits": [{"modify": "CORE-1", "set": {"text": "The core shall stamp each widget twice."},
                                    "reason": "the engineer wants double stamps"}],
                         "acks": {"CORE-V1": "the test now checks two stamps"}})
    text = changes.view(spec.load(), changes.current(spec.load()))
    assert "the engineer wants double stamps" in text
    assert "~~The core shall stamp each widget.~~ → The core shall stamp each widget twice." in text


def test_change_view_keeps_the_structure_of_multi_line_text(spec, change):
    change.data["entries"] = [{"op": "add", "id": "DR-1", "reason": "design",
                               "after": {"decision": "Three parts:\n- one\n- two"}}]
    text = changes.view(spec.load(), change)
    assert "  - decision:\n    Three parts:\n    - one\n    - two" in text


def test_an_open_decision_can_be_rewritten_in_place_until_answered(change):
    changes.add_decision(change, _decision())
    changes.add_decision(change, _decision(question="Paint or not?"))
    assert changes.add_decision(change, _decision(question="Stamp twice, once, or never?"), replace="D1") == "D1"
    ds = change.data["decisions"]
    assert [d["id"] for d in ds] == ["D1", "D2"] and ds[0]["question"] == "Stamp twice, once, or never?"
    with pytest.raises(changes.ChangeError, match="no decision D9"):
        changes.add_decision(change, _decision(), replace="D9")
    changes.resolve(change, ["D2"], "paint it", None, by="Ada <ada@example.com>")
    with pytest.raises(changes.ChangeError, match="already"):
        changes.add_decision(change, _decision(), replace="D2")


def test_an_overtaken_decision_is_withdrawn_with_a_reason(change):                     # CHANGE-21
    changes.add_decision(change, _decision())
    with pytest.raises(changes.ChangeError, match="say why"):
        changes.withdraw(change, "D1", "")
    changes.withdraw(change, "D1", "the engineer answered it in a comment")
    d = change.data["decisions"][0]
    assert d["status"] == "withdrawn" and d["withdrawn_because"].startswith("the engineer")
    with pytest.raises(changes.ChangeError, match="already withdrawn"):
        changes.withdraw(change, "D1", "again")


def test_a_decision_can_be_checked_without_recording_it(spec, capsys):
    from syseng import cli
    spec.write()
    changes.start(spec.load(), "Make better widgets", None, None, None)
    path = spec.root.parent / "d.yaml"
    import yaml
    path.write_text(yaml.safe_dump(_decision()))
    assert cli.main(["--spec", str(spec.root), "decide", "--dry-run", "--file", str(path)]) == 0
    assert "nothing was written" in capsys.readouterr().out
    assert not changes.current(spec.load()).data.get("decisions")
