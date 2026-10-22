"""The review page replaced the Markdown views (REVIEW-1, REVIEW-3, REVIEW-14, REVIEW-16, REVIEW-17; DR-60)."""

from pathlib import Path

from syseng import check, cli, model, pagedata, render, yamlio

JS = (Path(render.__file__).parent / "web" / "review.js").read_text()


def test_the_page_reads_top_down(spec):
    spec.write()
    data = pagedata.build(spec.load(), "Ada <ada@example.com>")
    assert [e["id"] for e in data["graph"]["elements"]] == ["SYS", "CORE"]        # the system first, then its parts
    assert data["graph"]["elements"][0]["items"] == ["NEED-1", "SYS-1"]           # needs before system requirements
    assert list(data)[1:] == list(pagedata.SECTIONS)                              # what awaits the person first


def test_the_page_knows_what_refines_each_item(spec):
    spec.write()
    items = pagedata.build(spec.load(), "Ada <ada@example.com>")["items"]
    assert items["CORE-1"]["parents"] == ["SYS-1"] and items["SYS-1"]["parents"] == ["NEED-1"]
    assert "CHILDREN[p]" in JS                                                      # the page inverts them to show what refines


def test_verification_items_are_hidden_until_asked_for(spec):
    assert JS.count("let showVI = false") == 2                                    # in the graph and in the full spec
    assert '"verification items"' in JS


def test_render_removes_the_markdown_views_and_writes_the_page(spec, capsys):
    root = spec.write()
    (root / "requirements.md").write_text("old view\n")
    (root / "decisions.md").write_text("old view\n")
    assert "R001" in spec.codes()
    assert cli.main(["--spec", str(root), "render"]) == 0
    assert not (root / "requirements.md").exists() and not (root / "decisions.md").exists()
    assert (root.parent / ".syseng" / "review.html").exists() and "R001" not in spec.codes()


def test_the_page_marks_each_items_level_and_what_its_under(spec):
    spec.files["approvals.yaml"] = [{"id": "SYS-1", "fingerprint": "000000000000", "locked_at": "2026-10-21T10:00-07:00",
                                     "by": "Ada <ada@example.com>", "via": "chat"}]
    spec.files["elements/CORE/requirements.yaml"].append({"id": "CORE-2", "text": "The core shall count each widget.",
                                                          "basis": "added", "traces_to": "SYS-1", "why": "inventory."})
    spec.write()
    items = pagedata.build(spec.load(), "Ada <ada@example.com>")["items"]
    assert (items["SYS-1"]["level"], items["SYS-1"]["given"], items["SYS-1"]["label"]) == (
        "stated", "explicit", "locked to an earlier version")                       # a changed lock decays (CHECK-28)
    assert (items["CORE-1"]["level"], items["CORE-1"]["under"]) == ("derived", "SYS-1")
    assert items["CORE-2"]["level"] == "added"
    assert "lv-${it.level}" in JS and '"changed since"' in JS                     # marks: level color, changed ring


def test_intent_reaches_the_page_with_who_when_and_context(spec):
    spec.files["elements/CORE/requirements.yaml"][0]["intent"] = [{
        "by": "Ada <ada@example.com>", "when": "2026-10-17 09:30", "basis": "stated", "fingerprint": "0" * 12,
        "context": "Talking about widget branding.", "said": "Wants every widget stamped."}]
    spec.write()
    rec = pagedata.build(spec.load(), "Ada <ada@example.com>")["items"]["CORE-1"]["intent"][0]
    assert (rec["by"], rec["when"], rec["context"]) == ("Ada <ada@example.com>", "2026-10-17 09:30",
                                                        "Talking about widget branding.")
    assert "rec.context" in JS and "rec.when" in JS and "rec.by" in JS
