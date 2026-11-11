"""Links into the review page, the focused view, and the agent's look-at-this list (SYS-63; REVIEW-56 to REVIEW-60,
CLI-39, CLI-40, AGENT-88, AGENT-89; DR-84, DR-85)."""

import json
import re
import shutil
import subprocess

import pytest

from syseng import changes, cli, init, links, model, page, pagedata

ADA = "Ada <ada@example.com>"
JS = (page.WEB / "review.js").read_text()


def _git(repo, *args):
    return subprocess.run(["git", "-c", "user.name=T", "-c", "user.email=t@example.com", *args], cwd=repo,
                          check=True, capture_output=True, text=True).stdout.strip()


@pytest.fixture
def repo(spec):
    root = spec.write()
    _git(root.parent, "init", "-q", "-b", "main")
    _git(root.parent, "add", "-A")
    _git(root.parent, "commit", "-qm", "base")
    return root


def _decision(change, question):
    return changes.add_decision(change, {"question": question, "importance": "i",
                                         "options": [{"label": "a", "recommended": True}, {"label": "b"}]})


@pytest.fixture
def history(repo):
    """Three changes: round 1 with an open D1 and a comment F1, two changes both numbered round 2, the second open
    with its own D1 and D2."""
    first = changes.start(model.load(repo), "first", None, None, "first")
    _decision(first, "First change's question?")
    first.data["feedback"] = [{"n": "F1", "by": ADA, "kind": "comment", "id": "CORE-1", "comment": "Why stamps?",
                               "response": "Stamped widgets sell."}]
    first.save()
    changes.close(first)
    a = changes.start(model.load(repo), "second", None, None, "a")
    changes.close(a)
    b = changes.Change(a.path.with_name(a.path.name.replace("-a.yaml", "-b.yaml")), {**a.data, "status": "open"})
    b.save()  # a second change numbered round 2, as two branches that each opened one leave behind
    _decision(b, "Newest change's first question?")
    _decision(b, "Newest change's second question?")
    return repo, first, a, b


# ---------------------------------------------------------------- link forms (REVIEW-58, DR-84)
def test_every_link_form_is_made_of_characters_that_reach_the_fragment(history):
    repo, first, a, b = history
    idx = links.index(model.load(repo))
    keys = list(idx["targets"]) + list(idx["aliases"])
    assert keys and all(links.ANCHOR_CHARS.fullmatch(k) for k in keys)         # no `/`, `=`, `?` or `&`
    assert f"{first.id}.D1" in idx["targets"] and f"{first.id}.F1" in idx["targets"]
    assert idx["targets"][f"{first.id}.F1"]["item"] == "CORE-1"
    assert links.focus(["CORE-1", f"{b.id}.D2"]) == f"focus~CORE-1~{b.id}.D2"


def test_short_forms_name_one_thing_or_list_every_candidate(history):
    repo, first, a, b = history
    aliases = links.index(model.load(repo))["aliases"]
    assert aliases["round-1.D1"] == [f"{first.id}.D1"]                         # a round only one change has
    assert "round-2.D1" not in aliases                                          # two changes share round 2
    assert aliases["D2"] == [f"{b.id}.D2"]                                      # only one D2 anywhere
    assert sorted(aliases["D1"]) == sorted([f"{first.id}.D1", f"{b.id}.D1"])   # another change has an open D1
    assert aliases["F1"] == [f"{first.id}.F1"]
    changes.resolve(first, ["D1"], "fine", None)
    assert links.index(model.load(repo))["aliases"]["D1"] == [f"{b.id}.D1"]    # the newest change's, as the CLI reads it


def test_targets_resolve_as_the_cli_names_them(history):
    repo, first, a, b = history
    s = model.load(repo)
    assert links.resolve(s, "CORE-1") == "CORE-1" and links.resolve(s, "CORE") == "CORE"
    assert links.resolve(s, "D2") == f"{b.id}/D2"
    assert links.resolve(s, "round-1/D1") == links.resolve(s, "round-1.D1") == f"{first.id}/D1"
    assert links.resolve(s, f"{first.id}.F1") == f"{first.id}/F1" and links.resolve(s, "round-1/F1") == f"{first.id}/F1"
    assert links.anchor(f"{first.id}/D1") == f"{first.id}.D1"
    for wrong in ("CORE-99", "D1", "F7", "round-2.D1"):  # unknown, ambiguous, missing, a round two changes share
        with pytest.raises(links.LinkError):
            links.resolve(s, wrong)


# ---------------------------------------------------------------- the page (REVIEW-56, REVIEW-57, REVIEW-58)
def _pure_functions() -> str:
    return JS[JS.index("// LINK-PURE-START"):JS.index("// LINK-PURE-END")]


@pytest.mark.skipif(shutil.which("node") is None, reason="needs Node (nix develop .#evals)")
def test_the_page_reads_every_link_form_and_resolves_it(history):
    repo, first, a, b = history
    data = pagedata.build(model.load(repo), ADA)
    cases = {"parse": [["#CORE-1", ""], ["#focus~CORE-1~D2", ""], ["#focus=CORE-1,D2", ""], ["", "?focus=CORE-1,D2"],
                       ["#CORE-1~D2", ""], ["#focus", ""], ["", ""], ["#round-1.D1", "?focus=SYS-1"]],
             "resolve": ["CORE-1", "core-1", f"{first.id}.D1", "round-1.D1", "D2", "D1", "F1", "round-2.D1", "NOPE-1"]}
    script = (_pure_functions() + f"\nconst items = {json.dumps(data['items'])};\nconst links = {json.dumps(data['meta']['links'])};"
              f"\nconst c = {json.dumps(cases)};\nconsole.log(JSON.stringify({{parse: c.parse.map(([h, s]) => parseLink(h, s)),"
              "resolve: c.resolve.map((t) => resolveLink(t, items, links))}));")
    out = json.loads(subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True).stdout)
    assert out["parse"] == [{"anchor": "CORE-1"}, {"focus": ["CORE-1", "D2"]}, {"focus": ["CORE-1", "D2"]},
                            {"focus": ["CORE-1", "D2"]}, {"focus": ["CORE-1", "D2"]}, None, None, {"anchor": "round-1.D1"}]
    item, lower, full, short, bare, both, comment, shared, unknown = out["resolve"]
    assert item == lower == {"kind": "item", "key": "CORE-1"}
    assert full == short == {"kind": "decision", "key": f"{first.id}.D1"}
    assert bare == {"kind": "decision", "key": f"{b.id}.D2"} and comment == {"kind": "comment", "key": f"{first.id}.F1"}
    assert sorted(both["ambiguous"]) == sorted([f"{first.id}.D1", f"{b.id}.D1"])
    assert shared is None and unknown is None


def test_the_page_opens_what_a_link_names_on_load_and_when_it_changes(history):
    repo, first, a, b = history
    data = pagedata.build(model.load(repo), ADA)
    assert f"{first.id}.D1" in data["meta"]["links"]["targets"]                 # the table the page resolves with
    assert 'window.addEventListener("hashchange", route)' in JS and "\n  route();" in JS
    route = JS[JS.index("function route()"):JS.index("// ---------------------------------------------------------------- go")]
    assert "parseLink(location.hash, location.search)" in route and "showFocus(link.focus)" in route
    jump = JS[JS.index("function jump(token)"):JS.index("function targetCard(")]
    assert 'showTab("items", true)' in jump and "revealInSpec(r.key)" in jump and "scrollToCard(card)" in jump
    assert "if (!r || r.ambiguous) return showFocus([token]);" in jump      # shown nowhere else: on its own
    for card in ("function decisionCard(d)", "function responseCard(r)"):
        assert '"data-anchor"' in JS[JS.index(card):JS.index(card) + 600]
    items = JS[JS.index("function renderItems()"):JS.index("function renderHeader()")]
    assert "if (it && id === pinned) return true;" in items and "body.append(details(id), itemActions(id))" in items


def test_a_focused_link_shows_only_what_it_names_with_a_way_back(history):
    focus = JS[JS.index("function showFocus(tokens)"):JS.index("function leaveLink()")]
    assert "for (const token of tokens)" in focus                              # in the order named
    assert '"Show everything"' in focus and "onclick: showEverything" in focus
    assert "isn't on this page" in focus and "could mean any of these" in focus
    back = JS[JS.index("function leaveLink()"):JS.index("function route()")]
    assert "renderAll();" in back and "history.replaceState" in back


# ---------------------------------------------------------------- spec review --link (CLI-39)
def test_review_link_prints_a_link_per_target_and_one_focused_on_all(history, capsys):
    repo, first, a, b = history
    url = "https://claude.ai/artifact/0123"
    assert cli.main(["--spec", str(repo), "review", "--link", "CORE-1", "round-1/D1", "--url", url + "#old"]) == 0
    out = capsys.readouterr().out.splitlines()
    assert out == [f"CORE-1 (The core shall stamp each widget.): {url}#CORE-1",
                   f"{first.id}/D1 (First change's question?): {url}#{first.id}.D1",
                   f"all 2, and nothing else: {url}#focus~CORE-1~{first.id}.D1"]
    assert cli.main(["--spec", str(repo), "review", "--link", "SYS-1"]) == 0   # no address: the fragments, and how
    out = capsys.readouterr().out
    assert "<address>#<fragment>" in out and ": #SYS-1\n" in out and "it alone: #focus~SYS-1" in out and "--url" in out
    page_file = repo.parent / "page.html"
    assert cli.main(["--spec", str(repo), "review", "--link", "SYS-1", "--out", str(page_file)]) == 0
    assert f"{page_file.resolve().as_uri()}#SYS-1" in capsys.readouterr().out
    assert not page_file.exists()                                             # writes nothing
    assert cli.main(["--spec", str(repo), "review", "--link", "SYS-1", "NOPE-1"]) == 1
    out = capsys.readouterr().out
    assert "NOPE-1" in out and "#SYS-1" not in out


# ---------------------------------------------------------------- the look-at-this list (CLI-40, REVIEW-59, REVIEW-60)
def test_point_records_a_ranked_look_at_this_list_apart_from_proposals(history, capsys):
    repo, first, a, b = history
    run = lambda *args: cli.main(["--spec", str(repo), "point", *args])
    assert run("CORE-1", "D2", "--why", "these decide the stamp") == 0
    assert run("round-1/D1", "--why", "settled earlier, but it bears on D2") == 0
    assert "number 2 on the look-at-this list" in capsys.readouterr().out
    marks = changes.current(model.load(repo)).data["look_at"]
    assert [m["targets"] for m in marks] == [["CORE-1", f"{b.id}/D2"], [f"{first.id}/D1"]]   # the order is the rank
    assert "proposals" not in changes.current(model.load(repo)).data                      # nothing asked to lock
    assert run("CORE-1") == 1 and "--why" in capsys.readouterr().out
    assert run("NOPE-1", "--why", "x") == 1
    assert run("CORE-1", "--why", "most important after all") == 0                        # marked again: moves
    marks = changes.current(model.load(repo)).data["look_at"]
    assert [m["targets"] for m in marks] == [[f"{b.id}/D2"], [f"{first.id}/D1"], ["CORE-1"]]
    assert run("D2", "--withdraw") == 0
    assert [m["targets"] for m in changes.current(model.load(repo)).data["look_at"]] == [[f"{first.id}/D1"], ["CORE-1"]]


def test_only_the_newest_changes_look_at_this_list_shows(history, capsys):
    repo, first, a, b = history
    assert cli.main(["--spec", str(repo), "point", "CORE-1", "--why", "an older mark"]) == 0
    data = pagedata.build(model.load(repo), ADA)
    assert data["look"]["change"] == b.id
    [mark] = data["look"]["marks"]
    assert mark["why"] == "an older mark" and mark["targets"] == [{"ref": "CORE-1", "anchor": "CORE-1", "kind": "item"}]
    changes.close(changes.current(model.load(repo)))
    newest = changes.start(model.load(repo), "next", None, None, None)
    data = pagedata.build(model.load(repo), ADA)
    assert data["look"] == {"change": newest.id, "marks": []}                  # each change starts clean
    assert cli.main(["--spec", str(repo), "point", f"{b.id}/D1", "SYS-1", "--why", "look here"]) == 0
    capsys.readouterr()
    data = pagedata.build(model.load(repo), ADA)
    assert [t["anchor"] for t in data["look"]["marks"][0]["targets"]] == [f"{b.id}.D1", "SYS-1"]
    assert data["look"]["marks"][0]["focus"] == f"focus~{b.id}.D1~SYS-1"
    assert cli.main(["--spec", str(repo), "review", "--section", "look"]) == 0
    out = capsys.readouterr().out
    assert f"from {newest.id}" in out and "1. " in out and "Newest change's first question?" in out
    for_you = JS[JS.index("function renderForYou()"):JS.index("function renderOverview(")]
    assert for_you.index("renderLook(el);") < for_you.index("renderOverview(el);") < for_you.index("Recommended by the agent")
    look = JS[JS.index("function renderLook(el)"):JS.index("function targetLink(t)")]
    assert "look.change" in look and 'class: "rank mono"' in look and "${n + 1}" in look and '"#" + m.focus' in look
    assert 'href: "#" + t.anchor' in JS[JS.index("function targetLink(t)"):JS.index("function decisionCard(d)")]


# ---------------------------------------------------------------- the skill (AGENT-88, AGENT-89)
def test_the_skill_says_to_paste_links_and_to_point_rather_than_propose():
    text = (init.SKILL / "SKILL.md").read_text()
    part = text[text.index("## Talking to the engineer"):]
    line = next(l for l in part.splitlines() if "spec review --link" in l)
    assert "bare IDs" in line and "spec point" in line and "without asking to lock" in line
    assert re.search(r"each change.s list starts empty", line)
