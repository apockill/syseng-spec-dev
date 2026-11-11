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


# ---------------------------------------------------------------- earlier rounds (CHANGE-25 to CHANGE-34)
# In the onboarding of a web-apps folder on 2026-11-03, a round's 7 open decisions went stale once the agent had
# closed it to start the next, and none could be withdrawn; round 2 had its own D1; 2 of 6 agents wanted to take
# back a lock proposal. What never reached the trunk is a draft, corrected without a trace; what reached it is kept.
def _git(root, *args):
    import subprocess
    subprocess.run(["git", "-c", "user.name=a", "-c", "user.email=a@b.c", *args], cwd=root, check=True,
                   capture_output=True)


def _two_rounds(spec, trunk=False):
    """Round one closed, round two open. With `trunk`, round one is committed on the trunk, as in a repository that
    commits straight to main."""
    spec.write()
    first = changes.start(spec.load(), "Round one", None, None, "one")
    changes.add_decision(first, _decision())
    changes.add_decision(first, _decision(question="Paint or not?"))
    changes.add_proposal(first, ["CORE-1"], "it is what the engineer sees")
    changes.close(first)
    if trunk:
        _git(spec.root.parent, "init", "-q", "-b", "main")
        _git(spec.root.parent, "add", ".")
        _git(spec.root.parent, "commit", "-qm", "round one")
    second = changes.start(spec.load(), "Round two", None, None, "two")
    changes.add_decision(second, _decision(question="Ship it?"))
    return first, second


def _run(spec, *argv):
    from syseng import cli
    return cli.main(["--spec", str(spec.root), *argv])


def _record(spec, change):
    return next(c for c in changes.all_changes(spec.load()) if c.id == change.id).data


def test_a_decision_is_named_across_rounds_by_its_change(spec, capsys):           # CHANGE-26
    first, second = _two_rounds(spec)
    loaded = spec.load()
    assert changes.find_decision(loaded, f"{first.id}/D2", second)[1]["question"] == "Paint or not?"
    assert changes.find_decision(loaded, "round-1-one/D1", second)[1]["question"] == "Stamp twice or once?"
    assert changes.find_decision(loaded, f"{first.id} D1", second)[0].id == first.id
    with pytest.raises(changes.ChangeError, match="could mean"):  # D1 is open in both rounds
        changes.find_decision(loaded, "D1", second)
    with pytest.raises(changes.ChangeError, match="could mean"):
        changes.find_decision(loaded, "D2", second)  # round two has no D2, round one's is open
    assert _run(spec, "status") == 0
    out = capsys.readouterr().out
    assert f"{first.id}/D1: Stamp twice or once?" in out and f"{first.id}/D2" in out


def test_a_drafts_decision_is_removed_without_a_trace(spec, capsys):               # CHANGE-30
    first, second = _two_rounds(spec)
    assert changes.on_trunk(spec.load(), first) is None
    assert _run(spec, "decide", "--withdraw", f"{first.id}/D1") == 0  # no reason needed
    assert "removed" in capsys.readouterr().out
    assert [d["id"] for d in _record(spec, first)["decisions"]] == ["D2"]
    assert "withdrawals" not in _record(spec, second)
    from syseng import pagedata
    assert (first.id, "D1") not in [(x["change"], x["id"]) for x in pagedata.awaiting(spec.load())["decisions"]]
    assert _run(spec, "decide", "--withdraw", "D1") == 0  # round two's own D1, now unambiguous
    changes.add_decision(changes.current(spec.load()), _decision(question="Ship it now?"))
    assert [d["id"] for d in _record(spec, second)["decisions"]] == ["D1"]  # numbering survives the removal


def test_a_drafts_decision_is_rewritten_in_place(spec, capsys, tmp_path):        # CHANGE-25, CHANGE-30
    first, second = _two_rounds(spec)
    path = tmp_path / "d.yaml"
    import yaml
    path.write_text(yaml.safe_dump(_decision(question="Paint it blue or not?")))
    assert _run(spec, "decide", "--replace", f"{first.id}/D2", "--file", str(path)) == 0
    assert f"rewrote open decision D2 in {first.id}" in capsys.readouterr().out
    d = _record(spec, first)["decisions"][1]
    assert d["question"] == "Paint it blue or not?" and d["status"] == "open"
    assert len(_record(spec, second)["decisions"]) == 1


def test_a_drafts_lock_proposal_is_removed_without_a_reason(spec, capsys):       # CHANGE-30, CHANGE-33
    first, second = _two_rounds(spec)
    from syseng import pagedata
    assert [p["id"] for p in pagedata.proposals(spec.load()) if p["from"] != "computed"] == ["CORE-1"]
    assert _run(spec, "propose", "CORE-1", "--withdraw") == 0
    assert "removed the proposal to lock CORE-1" in capsys.readouterr().out
    assert not _record(spec, first).get("proposals") and "withdrawals" not in _record(spec, second)
    assert not [x for x in pagedata.proposals(spec.load()) if x["from"] != "computed"]
    assert _run(spec, "propose", "CORE-1", "--withdraw") == 1
    assert "no proposal to lock CORE-1 is waiting" in capsys.readouterr().out


def test_a_trunk_decision_is_withdrawn_with_a_reason_and_logged(spec, capsys):     # CHANGE-32, CHANGE-29
    first, second = _two_rounds(spec, trunk=True)
    assert changes.on_trunk(spec.load(), first) is not None
    assert changes.on_trunk(spec.load(), second) is None
    assert _run(spec, "decide", "--withdraw", f"{first.id}/D1") == 1
    assert "on the trunk" in capsys.readouterr().out
    assert _run(spec, "decide", "--withdraw", f"{first.id}/D1", "--reason", "settled by the facts") == 0
    assert f"withdrew open decision {first.id}/D1; logged in {second.id}" in capsys.readouterr().out
    d = _record(spec, first)["decisions"][0]
    # what was asked stays as it was; the record gains only the status, why and where
    assert d["question"] == "Stamp twice or once?" and len(d["options"]) == 2
    assert d["status"] == "withdrawn" and d["withdrawn_because"] == "settled by the facts"
    assert d["withdrawn_in"] == second.id and "chosen" not in d and "words" not in d
    log = _record(spec, second)["withdrawals"]
    assert log[0]["decision"] == f"{first.id}/D1" and log[0]["because"] == "settled by the facts"
    from syseng import pagedata
    loaded = spec.load()
    awaiting = [(x["change"], x["id"]) for x in pagedata.awaiting(loaded)["decisions"]]
    assert (first.id, "D1") not in awaiting and (first.id, "D2") in awaiting
    assert "Withdrawn here" in changes.view(loaded, changes.current(loaded))
    _run(spec, "status")
    assert f"{first.id}/D1" not in capsys.readouterr().out


def test_a_trunk_decision_is_replaced_by_one_in_the_open_change(spec, capsys, tmp_path):  # CHANGE-25, CHANGE-32
    first, second = _two_rounds(spec, trunk=True)
    path = tmp_path / "d.yaml"
    import yaml
    path.write_text(yaml.safe_dump(_decision(question="Paint it blue or not?")))
    assert _run(spec, "decide", "--replace", f"{first.id}/D2", "--file", str(path)) == 0
    assert f"added open decision D2 to {second.id}, replacing {first.id}/D2" in capsys.readouterr().out
    new = _record(spec, second)["decisions"][1]
    assert new["question"] == "Paint it blue or not?" and new["replaces"] == f"{first.id}/D2"
    old = _record(spec, first)["decisions"][1]
    assert old["question"] == "Paint or not?" and old["status"] == "withdrawn"
    assert old["withdrawn_because"] == f"replaced by {second.id}/D2"
    assert _run(spec, "decide", "--replace", f"{first.id}/D2", "--file", str(path)) == 1
    assert "already withdrawn" in capsys.readouterr().out


def test_withdrawing_never_resolves_and_a_withdrawn_decision_takes_no_choice(spec, capsys):  # CHANGE-27
    first, second = _two_rounds(spec, trunk=True)
    _run(spec, "decide", "--withdraw", f"{first.id}/D1", "--reason", "duplicated in round two")
    capsys.readouterr()
    assert _run(spec, "resolve", f"{first.id}/D1", "--words", "fine") == 1
    assert "withdrawn, so there's nothing to choose" in capsys.readouterr().out
    assert _run(spec, "resolve", f"{first.id}/D2", "--words", "paint it") == 0
    d = _record(spec, first)["decisions"][1]
    assert d["status"] == "resolved" and d["words"] == "paint it"


def test_a_trunk_lock_proposal_is_withdrawn_with_a_reason(spec, capsys):         # CHANGE-32, CHANGE-33, CHANGE-29
    first, second = _two_rounds(spec, trunk=True)
    from syseng import pagedata
    assert _run(spec, "propose", "CORE-1", "--withdraw") == 1
    assert "say why" in capsys.readouterr().out
    assert _run(spec, "propose", "CORE-1", "--withdraw", "--reason", "the reason was wrong") == 0
    p = _record(spec, first)["proposals"][0]
    assert p["ids"] == ["CORE-1"] and p["why"] == "it is what the engineer sees"
    assert p["withdrawn"][0]["because"] == "the reason was wrong"
    assert _record(spec, second)["withdrawals"][0]["proposal"] == ["CORE-1"]
    loaded = spec.load()
    assert not [x for x in pagedata.proposals(loaded) if x["from"] != "computed"]
    assert "Proposed for you to lock" not in changes.view(loaded, next(c for c in changes.all_changes(loaded)
                                                                         if c.id == first.id))
    _run(spec, "status")
    assert "Proposed for locking" not in capsys.readouterr().out
    assert _run(spec, "propose", "CORE-1", "--why", "the right reason this time") == 0  # proposed afresh
    assert [x["why"] for x in pagedata.proposals(spec.load()) if x["from"] != "computed"] == ["the right reason this time"]


def test_a_draft_change_is_discarded_and_one_on_the_trunk_is_not(spec, capsys):  # CHANGE-31
    first, second = _two_rounds(spec, trunk=True)
    assert _run(spec, "change", "discard") == 0
    assert f"discarded {second.id}" in capsys.readouterr().out
    assert changes.current(spec.load()) is None and not second.path.exists()
    changes.start(spec.load(), "Round two again", None, None, "two")
    _git(spec.root.parent, "add", ".")
    _git(spec.root.parent, "commit", "-qm", "round two")
    assert _run(spec, "change", "discard") == 1
    assert "on the trunk" in capsys.readouterr().out


def test_starting_a_change_while_a_draft_is_open_says_to_keep_working_in_it(spec):  # CHANGE-34
    spec.write()
    changes.start(spec.load(), "Round one", None, None, "one")
    with pytest.raises(changes.ChangeError, match="Keep working in it") as e:
        changes.start(spec.load(), "Round two", None, None, "two")
    assert "spec change discard" in str(e.value)


def test_one_of_two_open_changes_can_be_closed_by_name(spec, change, capsys):            # CHANGE-35
    # merging two branches that each opened a change leaves both open; the toolkit then names the way out
    other = change.path.with_name("2026-01-01-round-99-other.yaml")
    other.write_text(change.path.read_text())
    with pytest.raises(changes.ChangeError, match=r"spec change close --id <id>"):
        changes.current(spec.load())
    assert _run(spec, "change", "close", "--id", "nosuch") == 1
    assert "no open change matches 'nosuch'" in capsys.readouterr().out
    assert _run(spec, "change", "close", "--id", other.stem) == 0
    assert changes.current(spec.load()).id == change.id
