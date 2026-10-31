"""Structure, trace and attribute checks (MODEL, SYS-6, CHECK-1)."""

from syseng import check, testlinks, yamlio


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
    assert "1 need nothing serves yet" in check.summarize(spec.findings())


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


def test_an_item_with_no_intent_and_no_basis_is_reported(spec):
    del spec.files["elements/CORE/requirements.yaml"][0]["origin"]
    spec.write()
    assert "A002" in spec.codes()
    spec.files["elements/CORE/requirements.yaml"][0]["basis"] = "derived"
    spec.write()
    assert "A002" not in spec.codes()


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


def test_requirement_above_the_leaves_that_nothing_refines_or_verifies_is_called_out(spec):
    spec.files["elements/SYS/requirements.yaml"].append(
        {"id": "SYS-2", "kind": "system", "text": "The system shall box widgets.", "origin": "engineer",
         "serves": ["NEED-1"], "source": '"boxes too"'})
    spec.files["elements/CORE/verification.yaml"] = []
    spec.write()
    todo = {f.item: f.message for f in spec.findings() if f.code == "T004"}
    assert "neither decomposed nor verified" in todo["SYS-2"]      # on SYS, which has CORE below it
    assert "neither" not in todo["SYS-1"]                          # CORE-1 refines it
    assert "neither" not in todo["CORE-1"]                         # a leaf element's requirement


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


def test_a_gendered_pronoun_in_a_need_requirement_or_intent_record_is_an_error(spec):   # CHECK-30
    spec.files["elements/CORE/requirements.yaml"][0]["text"] = "The core shall stamp each widget his way."
    spec.write()
    found = [f for f in spec.findings() if f.code == "W011"]
    assert found and found[0].item == "CORE-1" and found[0].severity == "error"
    spec.files["elements/CORE/requirements.yaml"][0]["text"] = "The core shall stamp each widget."
    spec.files["elements/SYS/needs.yaml"][0]["text"] = "The engineer needs widgets the way they like them."
    spec.write()
    assert "W011" not in spec.codes()                       # "they" and "the engineer" are fine


def test_tests_no_verification_item_links_are_listed_per_file(spec):                   # CHECK-3
    spec.files["elements/CORE/verification.yaml"][0]["tests"] = {"python": ["tests/test_core.py::test_stamp"]}
    spec.write()
    todo = [f.message for f in spec.findings() if f.code == "V003"]
    assert todo == ["tests/test_core.py has 1 test no verification item links: test_other"]


def test_unittest_classes_count_as_tests_for_the_unlinked_list(spec):                   # CHECK-3
    spec.write()
    tests = spec.root.parent / "tests" / "test_core.py"
    tests.write_text("import unittest\n\n\nclass AppsTest(unittest.TestCase):\n    def test_a(self):\n        pass\n")
    todo = [f.message for f in spec.findings() if f.code == "V003"]
    assert todo == ["tests/test_core.py has 1 test no verification item links: AppsTest::test_a"]


def test_a_need_drafted_from_agent_documents_may_say_it_is_derived(spec):
    need = spec.files["elements/SYS/needs.yaml"][0]
    for k in ("origin", "source", "context"):
        need.pop(k, None)
    need.update({"basis": "derived", "why": "read from a README an agent account wrote"})
    spec.write()
    assert "A002" not in spec.codes()


def test_an_item_can_allow_a_wording_rule_with_a_reason(spec):                         # CHECK-31
    req = spec.files["elements/CORE/requirements.yaml"][0]
    req["text"] = "The core shall label each widget with his or her name as the buyer typed it."
    spec.write()
    assert "W011" in spec.codes()
    req["allow"] = [{"rule": "W011", "why": "the requirement is about how the product writes pronouns"}]
    spec.write()
    assert "W011" not in spec.codes()
    req["allow"] = [{"rule": "W011"}]                       # no reason: refused
    spec.write()
    assert "W011" in spec.codes() and "S007" in spec.codes()


def test_a_roll_up_verifies_a_parent_only_while_every_child_is_verified(spec):         # CHECK-32
    spec.files["elements/SYS/verification.yaml"] = [{
        "id": "SYS-V1", "verifies": ["SYS-1"], "method": "analysis", "technique": "roll-up", "origin": "agent",
        "description": "SYS-1 holds when every requirement refining it is verified."}]
    spec.write()
    assert "V004" not in spec.codes(severity="todo") and "V001" not in spec.codes()
    spec.files["elements/CORE/verification.yaml"] = []
    spec.write()
    assert "V004" in spec.codes(severity="todo")


def test_a_parent_without_verification_is_told_how_to_resolve_it(spec):                # CHECK-32
    spec.write()
    msg = next(f.message for f in spec.findings() if f.code == "T004" and f.item == "SYS-1")
    assert "1 requirement refine it" in msg and "roll-up" in msg


def test_only_links_that_name_a_file_are_looked_up():
    assert testlinks.names_file("tests/test_x.py::test_y") and testlinks.names_file("tests/test_x.py")
    assert not testlinks.names_file("//backend/api:stop_test") and not testlinks.names_file("infra/apply")
