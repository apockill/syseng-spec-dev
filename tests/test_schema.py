"""One definition of each type of node (MODEL-44), reserved element names (MODEL-45), and types named wherever
nodes are shown (CLI-34, CLI-35, REVIEW-49 to REVIEW-51)."""

import json

from syseng import check, cli, edit, pagedata, page, schema


def test_every_type_has_a_label_a_description_and_fields():
    assert set(schema.TYPES) == {"element", "need", "system", "constraint", "requirement", "vi", "decision"}
    for kind in schema.TYPES:
        assert schema.label(kind) and schema.describe(kind) and schema.fields(kind)


def test_the_edit_command_takes_its_fields_from_the_schema():
    for kind in schema.TYPES:
        assert edit.FIELDS[kind] == schema.fields(kind)


def test_problems_name_the_field_and_what_is_wrong():
    vi = {"verifies": [], "method": "guess", "technique": "unit test", "description": "d"}
    assert schema.problems("vi", vi) == ["has an empty `verifies`",
                                         "has method 'guess'; use one of test, analysis, demonstration, inspection"]
    assert schema.problems("requirement", {"text": "t", "colour": "red"}) == [
        "has a field the requirement type doesn't have: `colour`"]
    assert schema.problems("element", {"title": "t"}) == ["has no `purpose`"]
    assert schema.problems("decision", {"title": "t", "decided_by": "agent", "elements": ["SYS"], "context": "c",
                                        "decision": "d", "requirements": ["SYS-1"]}) == []


def test_the_checker_reports_problems_with_the_type(spec):
    spec.files["elements/CORE/requirements.yaml"][0]["colour"] = "red"
    spec.files["elements/CORE/element.yaml"].pop("purpose")
    spec.write()
    messages = [f.message for f in spec.findings() if f.code == "S007"]
    assert "CORE-1 (requirement) has a field the requirement type doesn't have: `colour`" in messages
    assert "CORE (element) has no `purpose`" in messages


def test_reserved_names_cannot_name_an_element(spec):
    root = spec.write()
    cli.main(["--spec", str(root), "change", "start", "Add a part"])
    result = None
    try:
        edit.run(root, {"edits": [{"add": "element", "id": "DR", "title": "t", "parent": "SYS", "purpose": "p",
                                   "reason": "r"}]})
    except edit.EditError as e:
        result = str(e)
    assert result and "DR can't name an element" in result
    spec.files["elements/DR/element.yaml"] = {"id": "DR", "title": "t", "parent": "SYS", "purpose": "p",
                                             "depends_on": []}
    spec.write()
    assert "S009" in spec.codes()


def test_spec_schema_prints_the_reference_and_json_schema(capsys):
    assert cli.main(["schema"]) == 0
    assert capsys.readouterr().out == schema.reference()
    assert cli.main(["schema", "--json"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert set(data) == set(schema.TYPES) and "verifies" in data["vi"]["properties"]


def test_show_names_the_type(spec, capsys):
    root = spec.write()
    cli.main(["--spec", str(root), "show", "CORE-1"])
    assert "[requirement, in CORE" in capsys.readouterr().out
    cli.main(["--spec", str(root), "show", "CORE"])
    assert "CORE-1 [requirement]" in capsys.readouterr().out


def test_the_review_page_carries_each_type_and_draws_it(spec):
    spec.write()
    data = pagedata.build(spec.load(), "Ada <ada@example.com>")
    types = data["meta"]["types"]
    assert types["system"]["id"] == "SYS-n" and types["vi"]["label"] == "verification item" and types["need"]["about"]
    script = (page.WEB / "review.js").read_text()
    css = (page.WEB / "review.css").read_text()
    for kind in schema.TYPES:
        assert f".shape-{kind}" in css
    for marker in ("typeBadge(it.kind)", "typeLine(ITEMS[id].kind)", "Shape: type", "kindOn.has(it.kind)"):
        assert marker in script, marker
