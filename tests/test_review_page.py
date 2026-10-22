"""The review page and its feedback loop (SYS-45 to SYS-47, SYS-51 to SYS-53, REVIEW-20 to REVIEW-27,
CLI-23 to CLI-25, CLI-27, CHECK-23, CHANGE-19, MODEL-39)."""

import json
import re
import subprocess

import pytest

from syseng import changes, check, cli, diff, feedback, levels, model, page, pagedata, yamlio

ADA = "Ada <ada@example.com>"


def _git(repo, *args):
    return subprocess.run(["git", "-c", "user.name=T", "-c", "user.email=t@example.com", *args], cwd=repo,
                          check=True, capture_output=True, text=True).stdout.strip()


@pytest.fixture
def repo(spec):
    spec.files["elements/CORE/requirements.yaml"][0]["intent"] = [{
        "by": ADA, "when": "2026-10-21 09:00", "basis": "guided", "context": "Planning widgets.",
        "said": "Wants each widget stamped.", "fingerprint": "0" * 12}]
    root = spec.write()
    _git(root.parent, "init", "-q", "-b", "main")
    _git(root.parent, "add", "-A")
    _git(root.parent, "commit", "-qm", "base")
    return root


def _block(root, **parts):
    s = model.load(root)
    base = {"review": "r1", "by": ADA, "repository": root.parent.name, "revision": _git(root.parent, "rev-parse", "HEAD"),
            "dirty": False, "generated": "2026-10-21T10:00-07:00", "items": [], "decisions": []}
    base.update(parts)
    for it in base["items"]:
        it.setdefault("fingerprint", levels.review.current_fingerprint(s, it["id"]))
    return "## Spec review by Ada\n\nLocked: ...\n\n```syseng-feedback\n" + yamlio.dumps(base) + "```\n"


# ---------------------------------------------------------------- the page
def test_the_page_is_one_offline_file_with_every_section_in_order(repo):
    data = pagedata.build(model.load(repo), ADA, ["main"])
    assert list(data)[1:] == list(pagedata.SECTIONS)
    html = page.render(data)
    assert not re.search(r"(src|href)=[\"']https?://", html) and "@import" not in html and "url(http" not in html
    embedded = json.loads(re.search(r'id="review-data">(.*?)</script>', html, re.S).group(1).replace("<\\/", "</"))
    assert embedded["meta"]["person"] == ADA and "CORE-1" in embedded["items"]
    assert [e["id"] for e in embedded["graph"]["elements"]] == ["SYS", "CORE"]
    assert embedded["graph"]["elements"][1]["depth"] == 1


def test_the_page_lists_conflicts_first_and_proposes_items_to_lock_with_reasons(repo):
    changes.start(model.load(repo), "widgets", None, None, None)
    c = changes.current(model.load(repo))
    changes.add_decision(c, {"question": "q", "importance": "i", "options": [{"label": "a", "recommended": True}, {"label": "b"}]})
    changes.add_decision(c, {"kind": "conflict", "question": "c", "importance": "i", "involves": ["SYS-1"],
                             "options": [{"label": "keep", "recommended": True}, {"label": "roll back"}]})
    data = pagedata.build(model.load(repo), ADA)
    assert [d["kind"] for d in data["awaiting"]["decisions"]] == ["conflict", None]
    props = data["proposals"]
    assert props and props[0]["id"] == "NEED-1" and "3 items sit beneath it" in props[0]["why"]  # most of the tree


def test_an_item_proposed_again_shows_with_its_newest_proposal(repo):
    first = changes.start(model.load(repo), "first", None, None, None)
    changes.add_proposal(first, ["CORE-1"], "the old reason")
    changes.close(first)
    second = changes.start(model.load(repo), "second", None, None, None)
    changes.add_proposal(second, ["SYS-1", "CORE-1"], "the new reason")
    props = [p for p in pagedata.proposals(model.load(repo)) if p["from"] != "computed"]
    assert [(p["id"], p["why"], p["change"]) for p in props] == [
        ("SYS-1", "the new reason", second.id), ("CORE-1", "the new reason", second.id)]


def test_every_section_is_available_to_agents_as_text_and_yaml(repo, capsys):
    for name in pagedata.SECTIONS:
        assert cli.main(["--spec", str(repo), "review", "--section", name]) == 0
    assert "CORE-1 [derived, changed]" in capsys.readouterr().out      # its guided intent decayed (CHECK-28)
    assert cli.main(["--spec", str(repo), "review", "--section", "graph", "--format", "yaml"]) == 0
    assert yamlio.loads(capsys.readouterr().out)["elements"][0]["id"] == "SYS"


def test_the_review_command_writes_the_page_beside_the_hook_ignored_by_version_control(repo, capsys):
    assert cli.main(["--spec", str(repo), "review"]) == 0
    out = repo.parent / ".syseng"
    assert (out / "review.html").exists() and list((out / "reviews").glob("*.json"))
    assert set((out / ".gitignore").read_text().split()) == {"review.html", "reviews/"}
    assert "file://" in capsys.readouterr().out


# ---------------------------------------------------------------- applying feedback
def test_a_lock_is_recorded_in_the_reviewers_name_and_a_stale_one_is_refused(repo):
    text = _block(repo, items=[{"id": "CORE-1", "lock": True}, {"id": "SYS-1", "lock": True, "fingerprint": "stale0000000"}])
    report = feedback.apply(model.load(repo), feedback.parse(text))
    assert report.locked == ["CORE-1"] and any("SYS-1: changed since" in r for r in report.refused)
    lock = [a for a in yamlio.read(model.load(repo).locks_path()) if a["id"] == "CORE-1"][0]
    assert (lock["by"], lock["via"], lock["review"]) == (ADA, "page", "r1")
    assert levels.level_of(model.load(repo), "CORE-1").level == levels.EXPLICIT


def test_an_unlock_takes_the_lock_off_and_keeps_the_history(repo):
    feedback.apply(model.load(repo), feedback.parse(_block(repo, items=[{"id": "CORE-1", "lock": True}])))
    feedback.apply(model.load(repo), feedback.parse(_block(repo, review="r2", items=[{"id": "CORE-1", "lock": False}])))
    s = model.load(repo)
    lv = levels.level_of(s, "CORE-1")
    assert (lv.level, lv.given) == (levels.DERIVED, levels.GUIDED) and len(levels.review.history(s, "CORE-1")) == 2


def test_a_choice_resolves_the_decision_unless_its_options_changed(repo):
    changes.start(model.load(repo), "widgets", None, None, None)
    c = changes.current(model.load(repo))
    d = {"question": "q", "importance": "i", "options": [{"label": "a", "recommended": True}, {"label": "b"}]}
    changes.add_decision(c, d)
    fp = pagedata.decision_fingerprint(d)
    stale = _block(repo, decisions=[{"change": c.id, "id": "D1", "fingerprint": "nope", "choose": 2}])
    assert any("options changed" in r for r in feedback.apply(model.load(repo), feedback.parse(stale)).refused)
    ok = _block(repo, review="r2", decisions=[{"change": c.id, "id": "D1", "fingerprint": fp, "choose": 2}])
    feedback.apply(model.load(repo), feedback.parse(ok))
    resolved = changes.current(model.load(repo)).data["decisions"][0]
    assert (resolved["status"], resolved["chosen"], resolved["by"]) == ("resolved", "b", ADA)


def test_comments_wait_for_a_response_and_the_next_page_shows_it(repo):
    text = _block(repo, items=[{"id": "CORE-1", "comment": "Why stamp at all?"}], general="Looks fine overall.")
    report = feedback.apply(model.load(repo), feedback.parse(text))
    assert report.to_answer == ["F1 (CORE-1)", "F2"]
    assert [f.code for f in check.check(model.load(repo)) if f.code == "F001"] == ["F001", "F001"]
    assert cli.main(["--spec", str(repo), "feedback", "respond", "F1", "Stamps", "prove", "origin."]) == 0
    feedback.respond(model.load(repo), "F2", "Thanks.")
    assert not [f for f in check.check(model.load(repo)) if f.code == "F001"]
    shown = pagedata.build(model.load(repo), ADA)["responses"]
    assert shown[0]["response"] == "Stamps prove origin."


def test_an_intent_record_the_person_disowns_is_removed_through_an_edit(repo):
    text = _block(repo, items=[{"id": "CORE-1", "intent": [{"record": 0, "action": "remove", "when": "2026-10-21 09:00",
                                                            "by": ADA}]}])
    report = feedback.apply(model.load(repo), feedback.parse(text))
    s = model.load(repo)
    assert report.removed_intent == ["CORE-1"] and "intent" not in s.items["CORE-1"].data
    entry = changes.current(s).data["entries"][-1]
    assert entry["id"] == "CORE-1" and "isn't what they meant" in entry["reason"]


def test_the_review_is_recorded_so_the_next_comparison_starts_there(repo):
    feedback.apply(model.load(repo), feedback.parse(_block(repo)))
    rec = yamlio.read(repo / "reviews.yaml")[-1]
    assert (rec["by"], rec["review"], rec["dirty"]) == (ADA, "r1", False) and "fingerprints" not in rec
    assert diff.since_review(model.load(repo), ADA).older.label == "your last review"


def test_a_block_must_name_a_person(repo):
    with pytest.raises(feedback.FeedbackError, match="Name <email>"):
        feedback.parse(_block(repo, by="Ada"))


# ---------------------------------------------------------------- round 23: item by item, beside the reader
JS = (page.WEB / "review.js").read_text()


def test_items_open_beside_the_reader_and_light_up_in_the_graph():
    assert "function openItem(id)" in JS and "Graph.select(id)" in JS          # REVIEW-28: opens in the side pane
    assert 'document.addEventListener("mouseover"' in JS and "Graph.hover(" in JS  # REVIEW-29: pointing highlights
    assert "scrollIntoView" not in JS                                           # the reader's place never moves
    html = (page.WEB / "review.html").read_text()
    assert 'id="graphbox"' in html and 'id="focus"' in html


def test_each_item_in_a_decision_is_answered_on_its_own():
    assert "Each item, on its own" in JS and "answered" in JS and "Suggest wording" in JS   # REVIEW-30
    assert "wording: ${JSON.stringify(s.wording)}" in JS


def test_a_suggested_wording_goes_to_the_agent_as_feedback(repo):
    text = _block(repo, items=[{"id": "CORE-1", "wording": "The core shall stamp each widget twice."}])
    report = feedback.apply(model.load(repo), feedback.parse(text))
    f = changes.current(model.load(repo)).data["feedback"][0]
    assert report.to_answer == ["F1 (CORE-1)"] and (f["kind"], f["comment"]) == ("wording", "The core shall stamp each widget twice.")


def test_choosing_a_conflict_option_keeps_and_rolls_back_the_items_it_names(repo):
    from syseng import cli as _cli
    assert _cli.main(["--spec", str(repo), "lock", "SYS-1", "--via", "chat"]) == 0
    changes.start(model.load(repo), "widgets", None, None, None)
    c = changes.current(model.load(repo))
    d = {"kind": "conflict", "question": "q", "importance": "i", "involves": ["SYS-1", "CORE-1"],
         "options": [{"label": "keep SYS-1, roll back CORE-1", "recommended": True, "keeps": ["SYS-1"],
                      "rolls_back": ["CORE-1"]}, {"label": "roll back both", "rolls_back": ["SYS-1", "CORE-1"]}]}
    changes.add_decision(c, d)
    with pytest.raises(changes.ChangeError, match="doesn't involve"):
        changes.add_decision(c, {**d, "options": [{"label": "x", "recommended": True, "keeps": ["NEED-1"]}, {"label": "y"}]})
    text = _block(repo, decisions=[{"change": c.id, "id": "D1", "fingerprint": pagedata.decision_fingerprint(d), "choose": 1}])
    report = feedback.apply(model.load(repo), feedback.parse(text))
    assert report.kept == ["SYS-1"] and report.to_answer == ["F1 (CORE-1)"]
    assert yamlio.read(model.load(repo).locks_path())[-1]["note"] == "kept under D1"


def test_since_a_review_of_uncommitted_work_shows_only_what_changed_after_it(repo):
    changes.start(model.load(repo), "widgets", None, None, None)
    from syseng import edit as _edit
    assert _edit.run(repo, {"edits": [{"modify": "CORE-1", "set": {"text": "The core shall stamp each widget twice."},
                                       "reason": "twice"}], "acks": {"CORE-1": "fine", "CORE-V1": "fine"}}).applied
    data = pagedata.build(model.load(repo), ADA)
    page.write(data, repo.parent / ".syseng" / "review.html", repo.parent / ".syseng" / "reviews")
    feedback.apply(model.load(repo), feedback.parse(_block(repo, review=data["meta"]["review"], dirty=True)))
    assert _edit.run(repo, {"edits": [{"modify": "SYS-1", "set": {"text": "The system shall make blue widgets."},
                                       "reason": "blue"}], "acks": {"CORE-1": "fine", "SYS-1": "fine"}}).applied
    d = diff.since_review(model.load(repo), ADA)
    assert [x.id for x in d.items] == ["SYS-1"] and "compared with what it showed" in d.older.note


# ---------------------------------------------------------------- round 24: one place for what's for you
def test_the_first_tab_holds_what_awaits_the_person_then_the_agents_recommendations(repo):
    names = re.search(r"const names = \{(.*?)\};", JS).group(1)                            # REVIEW-20: by signal
    assert re.findall(r"(\w+): \"", names) == ["awaiting", "altered", "captured", "changes", "items"]
    for_you = JS[JS.index("function renderForYou()"):JS.index("function subItem(")]
    assert for_you.index("Recommended by the agent") < for_you.index("Decisions waiting") < for_you.index("Answers to your feedback")
    assert "Lock all" in JS and "Earlier recommendations, still unlocked" in JS
    assert "function triage(" in JS and '"answered"' in (page.WEB / "review.css").read_text()   # REVIEW-31
    changes.start(model.load(repo), "widgets", None, None, None)
    changes.add_proposal(changes.current(model.load(repo)), ["SYS-1", "NEED-1"], "the top of the tree")
    props = pagedata.build(model.load(repo), ADA)["proposals"]
    judged = [p for p in props if p["from"] != "computed"]
    assert [p["id"] for p in judged] == ["SYS-1", "NEED-1"] and judged[0]["change"] == changes.current(model.load(repo)).id
    assert len([p for p in props if p["from"] == "computed"]) <= 5


def test_the_item_in_focus_is_tall_and_its_split_with_the_graph_can_be_dragged():
    css = (page.WEB / "review.css").read_text()
    html = (page.WEB / "review.html").read_text()
    assert 'id="splitter"' in html and "height: 60%" in css and "row-resize" in css   # REVIEW-28
    assert "syseng-split" in JS and "pointermove" in JS


def test_feedback_already_applied_is_dropped_from_the_page(repo):
    assert "state.copied" in JS and "META.applied" in JS                          # REVIEW-23
    feedback.apply(model.load(repo), feedback.parse(_block(repo, review="r7")))
    assert pagedata.build(model.load(repo), ADA)["meta"]["applied"] == ["r7"]


# ---------------------------------------------------------------- round 27 nits
def test_clicking_an_items_card_opens_it_like_its_id():
    click = JS[JS.index('document.addEventListener("click"'):]
    assert 'closest("[data-item]")' in click and "openItem(t.dataset.item)" in click   # REVIEW-29


def test_typing_a_wording_never_rebuilds_the_list_it_is_typed_in():
    group = JS[JS.index("const refresh = () =>"):JS.index("lockAll.addEventListener")]
    assert "replaceChildren" not in group.split("const rebuild")[0]                    # REVIEW-30: refresh only
    assert "subItem(id, {}, refresh)" in group


def test_copy_feedback_copies_at_once():
    copy_fn = JS[JS.index("function openCopy()"):JS.index("function showBlock(")]
    assert "copy(text" in copy_fn and "showModal" not in copy_fn                      # SYS-51
    assert "showBlock(text)" in JS                                                     # only when the browser won't copy


def test_feedback_sent_again_is_not_recorded_twice(repo):
    text = _block(repo, items=[{"id": "CORE-1", "lock": True, "comment": "Why stamp?"}])
    feedback.apply(model.load(repo), feedback.parse(text))
    again = feedback.apply(model.load(repo), feedback.parse(_block(repo, review="r2", items=[{"id": "CORE-1", "lock": True,
                                                                                         "comment": "Why stamp?"}])))
    assert again.locked == [] and again.to_answer == [] and "CORE-1 locked" in again.already


# ---------------------------------------------------------------- round 28: the overview
def test_the_overview_measures_the_spec_and_marks_what_got_worse(repo):
    from syseng import health
    now = health.metrics(model.load(repo))
    assert (now["requirements"], now["vis"], now["unverified"], now["tests"]) == (2, 1, 1, 1)
    assert now["coverage"] == 50.0 and sum(now["mix"].values()) == 3
    measures = {m["key"]: m for m in health.compare(now, {**now, "unverified": 0, "coverage": 100.0, "tests": 0})}
    assert measures["unverified"]["worse"] and measures["coverage"]["worse"] and measures["tests"]["improved"]
    assert health.compare(now, {**now, "unverified": 0})[0]["key"] == "unverified"        # what got worse comes first


def test_the_page_opens_on_the_overview_and_agents_can_read_it(repo, capsys):
    data = pagedata.build(model.load(repo), ADA)
    o = data["overview"]
    assert list(data)[1] == "overview" and o["measures"] and o["now"]["mix"]
    assert "renderOverview(el);" in JS and "· worse" in JS and "All measures" in JS     # REVIEW-32
    assert cli.main(["--spec", str(repo), "review", "--section", "overview"]) == 0
    assert "Verification coverage: 50.0%" in capsys.readouterr().out
