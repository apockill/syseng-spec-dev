"""Structure, trace and attribute checks (MODEL, SYS-6, CHECK-1)."""

from syseng import check, yamlio


def test_valid_spec_has_no_errors(spec):
    spec.write()
    assert spec.codes() == []


def test_nested_element_directory_is_reported(spec):
    spec.files["elements/CORE/SUB/element.yaml"] = {"id": "SUB", "title": "Sub", "parent": "CORE",
                                                    "depends_on": [], "purpose": "x"}
    spec.write()
    assert "S004" in spec.codes()


def test_broken_tree_is_reported(spec):
    spec.files["elements/CORE/element.yaml"]["parent"] = "NOPE"
    spec.write()
    assert "S005" in spec.codes()


def test_parent_loop_is_reported(spec):
    spec.files["elements/SYS/element.yaml"]["parent"] = "CORE"
    spec.write()
    assert "S005" in spec.codes()


def test_unknown_dependency_is_reported(spec):
    spec.files["elements/CORE/element.yaml"]["depends_on"] = ["GHOST"]
    spec.write()
    assert "S006" in spec.codes()


def test_dependency_cycle_is_reported(spec):
    spec.files["elements/CORE/element.yaml"]["depends_on"] = ["UTIL"]
    spec.files["elements/UTIL/element.yaml"] = {"id": "UTIL", "title": "Util", "parent": "SYS",
                                                "depends_on": ["CORE"], "purpose": "Helps."}
    spec.write()
    cycles = [f for f in spec.findings() if f.code == "S006"]
    assert cycles and "CORE" in cycles[0].message and "UTIL" in cycles[0].message


def test_unserved_need_is_reported(spec):
    spec.files["elements/SYS/needs.yaml"].append({"id": "NEED-2", "text": "The engineer needs gadgets.",
                                                  "origin": "engineer", "source": '"gadgets"'})
    spec.write()
    assert "T002" in spec.codes(severity="todo") and "T002" not in spec.codes()
    assert "1 needs nothing serves yet" in check.summarize(spec.findings())


def test_untraced_requirement_is_reported(spec):
    del spec.files["elements/CORE/requirements.yaml"][0]["traces_to"]
    spec.write()
    assert "T001" in spec.codes()


def test_derived_requirement_needs_a_reason(spec):
    req = spec.files["elements/CORE/requirements.yaml"][0]
    del req["traces_to"]
    req["derived"] = True
    req["why"] = "a design choice: stamping happens at the core."
    spec.write()
    assert "T001" not in spec.codes()
    del req["why"]
    req["source"] = '"x"'
    spec.write()
    assert "T001" in spec.codes()


def test_requirement_without_rationale_is_reported(spec):
    del spec.files["elements/CORE/requirements.yaml"][0]["why"]
    spec.write()
    assert "A001" in spec.codes()


def test_missing_origin_is_reported(spec):
    spec.files["elements/CORE/requirements.yaml"][0]["origin"] = "someone"
    spec.write()
    assert "A002" in spec.codes()


def test_retired_id_reuse_is_reported(spec):
    spec.files["retired.yaml"] = [{"element": "CORE", "ids": ["CORE-1"], "note": "CORE-1, in round 1."}]
    spec.write()
    assert "S003" in spec.codes()


def test_duplicate_id_is_reported(spec):
    spec.files["elements/CORE/requirements.yaml"].append(dict(spec.files["elements/CORE/requirements.yaml"][0]))
    spec.write()
    assert "S002" in spec.codes()


def test_item_in_the_wrong_element_is_reported(spec):
    spec.files["elements/CORE/requirements.yaml"][0]["id"] = "OTHER-1"
    spec.files["elements/CORE/verification.yaml"][0]["verifies"] = ["OTHER-1"]
    spec.write()
    assert "S008" in spec.codes()


def test_invalid_verification_item_is_reported(spec):
    vi = spec.files["elements/CORE/verification.yaml"][0]
    vi["method"] = "vibes"
    vi["technique"] = "hope"
    spec.write()
    assert spec.codes().count("V001") == 2


def test_requirement_without_verification_is_a_todo_not_an_error(spec):
    spec.files["elements/CORE/verification.yaml"] = []
    spec.write()
    assert "T004" not in spec.codes()
    assert "T004" in spec.codes(severity="todo")


def test_one_run_reports_every_problem(spec):
    spec.files["elements/CORE/element.yaml"]["depends_on"] = ["GHOST"]
    spec.files["elements/CORE/requirements.yaml"][0]["origin"] = None
    spec.files["elements/CORE/requirements.yaml"][0]["text"] = "The core shall stamp widgets etc."
    spec.write()
    codes = set(spec.codes())
    assert {"S006", "A002", "W004"} <= codes


def test_stale_view_is_reported(spec):
    root = spec.write()
    (root / "requirements.md").write_text("hand-edited\n")
    assert "R001" in spec.codes()


def test_malformed_file_is_reported_without_crashing(spec):
    root = spec.write()
    (root / "elements" / "CORE" / "requirements.yaml").write_text("- id: [unclosed\n")
    assert "S001" in spec.codes()


def test_yaml_round_trip_keeps_prose_readable(tmp_path):
    path = tmp_path / "x.yaml"
    yamlio.write(path, [{"id": "A-1", "source": '"it\'s quoted: really"'}])
    text = path.read_text()
    assert "''" not in text and "\\" not in text
    assert yamlio.read(path)[0]["source"] == '"it\'s quoted: really"'
