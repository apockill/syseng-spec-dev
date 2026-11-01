"""Verification status from test results (SYS-57), through readers (SYS-58)."""

import json
import subprocess
import textwrap

import pytest
import yaml

from syseng import cli, model, readers, results

JUNIT = """<testsuites><testsuite>
<testcase classname="tests.test_a" name="test_one"/>
<testcase classname="tests.test_a" name="test_two"><failure message="no"/></testcase>
<testcase classname="tests.test_a.TestThing" name="test_three[x]"/>
<testcase classname="tests.test_a.TestThing" name="test_three[y]"><error/></testcase>
<testcase classname="tests.test_a" name="test_four"><skipped/></testcase>
<testcase name="bare"/>
</testsuite></testsuites>"""


@pytest.fixture
def repo(tmp_path, monkeypatch):
    spec = tmp_path / "spec"
    (spec / "elements" / "SYS").mkdir(parents=True)
    (spec / "toolkit.yaml").write_text(yaml.safe_dump({
        "spec_version": 2, "element_order": ["SYS"],
        "implementations": [{"name": "aws", "root": ".", "primary": True}, {"name": "gcp", "root": "."}]}))
    (spec / "elements" / "SYS" / "element.yaml").write_text("id: SYS\ntitle: S\npurpose: P\n")
    (spec / "elements" / "SYS" / "needs.yaml").write_text(
        "- id: NEED-1\n  text: The engineer needs it.\n  context: c\n  basis: derived\n  why: w\n")
    (spec / "elements" / "SYS" / "requirements.yaml").write_text(textwrap.dedent("""\
        - id: SYS-1
          kind: system
          text: The tool shall do one.
          serves: [NEED-1]
          basis: derived
          why: w
        - id: SYS-2
          kind: system
          text: The tool shall do two.
          serves: [NEED-1]
          basis: derived
          why: w
        """))
    (spec / "elements" / "SYS" / "verification.yaml").write_text(textwrap.dedent("""\
        - id: SYS-V1
          verifies: [SYS-1]
          method: test
          technique: unit test
          description: One.
          tests:
            aws: ["//api:one_test"]
        - id: SYS-V2
          verifies: [SYS-2]
          method: test
          technique: integration test
          description: Two.
          tests:
            aws: ["//api:two_test", "infra/apply"]
        - id: SYS-V3
          verifies: [SYS-2]
          method: inspection
          technique: reasoning check
          description: Judge it.
        """))
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "-c", "user.name=a", "-c", "user.email=a@b.c", "commit", "-q", "--allow-empty", "-m", "x"],
                   cwd=tmp_path, check=True)
    monkeypatch.chdir(tmp_path)
    return tmp_path


def _add(*args, revision="r1"):
    return cli.main(["results", "add", "--revision", revision, *args])


def _status(capsys, *args):
    capsys.readouterr()
    code = cli.main(["results", "status", "--json", *args])
    return code, json.loads(capsys.readouterr().out)


def _by_id(data, implementation="aws"):
    return {r["id"]: r for r in data[implementation]["items"]}


def test_junit_identifiers_and_outcomes(tmp_path):
    path = tmp_path / "r.xml"
    path.write_text(JUNIT)
    assert readers.read("junit", path, tmp_path) == {
        "tests.test_a.test_one": "pass", "tests.test_a.test_two": "fail", "tests.test_a.TestThing.test_three[x]": "pass",
        "tests.test_a.TestThing.test_three[y]": "fail", "tests.test_a.test_four": "skip", "bare": "pass"}


def test_pytest_junit_gives_node_ids_and_a_parametrized_test_its_worst_outcome(tmp_path):
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_a.py").write_text("")
    path = tmp_path / "r.xml"
    path.write_text(JUNIT)
    found = readers.read("pytest-junit", path, tmp_path)
    assert found["tests/test_a.py::test_one"] == "pass"
    assert found["tests/test_a.py::TestThing::test_three"] == "fail"


def test_jsonl_reads_one_result_per_line_and_says_which_line_is_wrong(tmp_path):
    path = tmp_path / "r.jsonl"
    path.write_text('{"id": "//a:b", "outcome": "pass"}\n\n{"id": "c", "outcome": "fail"}\n')
    assert readers.read("jsonl", path, tmp_path) == {"//a:b": "pass", "c": "fail"}
    path.write_text('{"id": "c", "outcome": "maybe"}\n')
    with pytest.raises(readers.ReaderError, match="line 1"):
        readers.read("jsonl", path, tmp_path)


def test_a_new_reader_is_found_without_changing_anything_else(monkeypatch, tmp_path):
    (tmp_path / "blaze_events.py").write_text("def read(path, root):\n    return {'//a:b': 'pass'}\n")
    monkeypatch.setattr(readers, "__path__", [*readers.__path__, str(tmp_path)])
    assert "blaze-events" in readers.names()
    assert readers.read("blaze-events", tmp_path / "x", tmp_path) == {"//a:b": "pass"}


def test_an_unknown_format_names_the_readers_and_the_way_to_ask(repo, capsys):
    (repo / "r.bin").write_text("x")
    assert _add("r.bin", "--format", "blaze", "--step", "unit") == 1
    out = capsys.readouterr().out
    assert "junit" in out and "spec issue" in out


def test_invalid_xml_is_reported(repo, capsys):
    (repo / "r.xml").write_text("<nope")
    assert _add("r.xml", "--step", "unit") == 1
    assert "isn't valid XML" in capsys.readouterr().out


def test_steps_add_up_in_any_order_into_one_status(repo, capsys):
    (repo / "a.jsonl").write_text('{"id": "//api:one_test", "outcome": "pass"}\n')
    (repo / "b.jsonl").write_text('{"id": "//api:two_test", "outcome": "pass"}\n')
    assert _add("a.jsonl", "--format", "jsonl", "--step", "unit") == 0
    assert _by_id(_status(capsys)[1])["SYS-V2"]["status"] == results.NOT_RUN
    assert _add("--step", "infra", "--id", "infra/apply", "--outcome", "pass") == 0
    assert _add("b.jsonl", "--format", "jsonl", "--step", "cheap") == 0
    items = _by_id(_status(capsys)[1])
    assert items["SYS-V1"]["status"] == items["SYS-V2"]["status"] == results.PASSING


def test_several_reports_in_one_command(repo, capsys):
    (repo / "a.jsonl").write_text('{"id": "//api:one_test", "outcome": "pass"}\n')
    (repo / "b.jsonl").write_text('{"id": "//api:two_test", "outcome": "pass"}\n{"id": "infra/apply", "outcome": "pass"}\n')
    assert _add("a.jsonl", "b.jsonl", "--format", "jsonl", "--step", "all") == 0
    assert _by_id(_status(capsys)[1])["SYS-V2"]["status"] == results.PASSING


def test_a_retry_replaces_its_step(repo, capsys):
    (repo / "a.jsonl").write_text('{"id": "//api:one_test", "outcome": "fail"}\n')
    (repo / "b.jsonl").write_text('{"id": "//api:two_test", "outcome": "pass"}\n')
    _add("a.jsonl", "--format", "jsonl", "--step", "unit")
    assert _status(capsys)[0] == 1
    _add("b.jsonl", "--format", "jsonl", "--step", "unit")
    code, data = _status(capsys)
    assert code == 0 and _by_id(data)["SYS-V1"]["status"] == results.NOT_RUN


def test_a_results_newest_outcome_decides_and_names_where_it_was_last_tested(repo, capsys):
    _add("--step", "unit", "--id", "//api:one_test", "--outcome", "fail", revision="old")
    _add("--step", "unit", "--id", "//api:one_test", "--outcome", "pass", revision="new")
    row = _by_id(_status(capsys)[1])["SYS-V1"]
    assert row["status"] == results.PASSING and row["last_tested"] == "new"


def test_an_older_result_still_counts(repo, capsys):
    _add("--step", "nightly", "--id", "//api:one_test", "--outcome", "pass", revision="old")
    _add("--step", "unit", "--id", "//api:two_test", "--outcome", "pass", revision="new")
    assert _by_id(_status(capsys)[1])["SYS-V1"]["last_tested"] == "old"


def test_a_skip_counts_as_not_run(repo, capsys):
    (repo / "a.jsonl").write_text('{"id": "//api:one_test", "outcome": "skip"}\n')
    _add("a.jsonl", "--format", "jsonl", "--step", "unit")
    assert _by_id(_status(capsys)[1])["SYS-V1"]["status"] == results.NOT_RUN


def test_status_counts_each_implementation_separately(repo, capsys):
    _add("--step", "unit", "--id", "//api:one_test", "--outcome", "pass")
    _, data = _status(capsys)
    assert data["aws"]["counts"] == {results.PASSING: 1, results.FAILING: 0, results.NOT_RUN: 2,
                                     results.NOT_IMPLEMENTED: 0}
    assert data["gcp"]["counts"] == {results.PASSING: 0, results.FAILING: 0, results.NOT_RUN: 1,
                                     results.NOT_IMPLEMENTED: 2}


def test_results_are_kept_per_implementation(repo, capsys):
    _add("--step", "unit", "--id", "//api:one_test", "--outcome", "fail", "--implementation", "gcp")
    assert _by_id(_status(capsys)[1])["SYS-V1"]["status"] == results.NOT_RUN
    assert _add("--step", "unit", "--id", "x", "--outcome", "pass", "--implementation", "azure") == 1


def test_failures_are_listed_by_level_of_intent_and_fail_the_command(repo, capsys):
    locks = repo / "spec" / "locks.yaml"
    spec = model.load(repo / "spec")
    from syseng import review
    locks.write_text(yaml.safe_dump([{"id": "SYS-2", "by": "Ada <ada@example.com>", "when": "2026-01-01", "via": "chat",
                                      "fingerprint": review.current_fingerprint(spec, "SYS-2"), "count": 1}]))
    _add("--step", "unit", "--id", "//api:one_test", "--outcome", "fail")
    _add("--step", "unit2", "--id", "//api:two_test", "--outcome", "fail")
    code, data = _status(capsys)
    assert code == 1
    assert [r["id"] for r in data["aws"]["failing"]] == ["SYS-V2", "SYS-V1"]
    assert data["aws"]["failing"][0]["failed"] == ["//api:two_test"]


def test_not_run_items_verifying_locked_requirements_are_listed(repo, capsys):
    from syseng import health, review
    spec = model.load(repo / "spec")
    (repo / "spec" / "locks.yaml").write_text(yaml.safe_dump([
        {"id": "SYS-1", "by": "Ada <ada@example.com>", "when": "2026-01-01", "via": "chat",
         "fingerprint": review.current_fingerprint(spec, "SYS-1"), "count": 1}]))
    code, data = _status(capsys)
    assert code == 0 and [r["id"] for r in data["aws"]["not_run_locked"]] == ["SYS-V1"]
    numbers = health.metrics(model.load(repo / "spec"))
    assert numbers["not_run"] == 3 and numbers["not_run_locked"] == 1


def test_the_review_page_overview_carries_the_status(repo):
    from syseng import pagedata
    data = pagedata.build(model.load(repo / "spec"), "Ada <ada@example.com>")
    assert data["overview"]["verification"]["aws"]["counts"][results.NOT_RUN] == 3


def test_a_verdict_is_a_result_named_by_the_item(repo, capsys):
    assert _by_id(_status(capsys)[1])["SYS-V3"]["status"] == results.NOT_RUN
    _add("--step", "review", "--id", "SYS-V3", "--outcome", "pass")
    assert _by_id(_status(capsys)[1])["SYS-V3"]["status"] == results.PASSING
    assert _status(capsys)[1]["aws"]["unlinked"] == []


def test_tests_nothing_links_are_listed(repo, capsys):
    _add("--step", "unit", "--id", "//api:new_test", "--outcome", "pass")
    assert _status(capsys)[1]["aws"]["unlinked"] == ["//api:new_test"]


def test_a_link_to_a_file_covers_its_tests(repo, capsys):
    path = repo / "spec" / "elements" / "SYS" / "verification.yaml"
    path.write_text(path.read_text().replace('"//api:one_test"', '"tests/a.py"'))
    _add("--step", "unit", "--id", "tests/a.py::test_x", "--outcome", "pass")
    data = _status(capsys)[1]
    assert _by_id(data)["SYS-V1"]["status"] == results.PASSING and data["aws"]["unlinked"] == []


def test_results_stay_out_of_version_control_and_can_live_elsewhere(repo, capsys):
    _add("--step", "unit", "--id", "//api:one_test", "--outcome", "pass")
    assert "results/" in (repo / ".syseng" / ".gitignore").read_text()
    other = repo / "shared"
    assert _add("--step", "unit", "--id", "//api:two_test", "--outcome", "pass", "--results-dir", str(other)) == 0
    assert list(other.rglob("*.json"))
    assert _by_id(_status(capsys, "--results-dir", str(other))[1])["SYS-V1"]["status"] == results.NOT_RUN


def test_a_revision_is_never_parsed(repo, capsys):
    assert _add("--step", "unit", "--id", "//api:one_test", "--outcome", "pass", revision="cl/12345:weird") == 0
    assert _by_id(_status(capsys)[1])["SYS-V1"]["last_tested"] == "cl/12345:weird"


def test_a_link_that_names_no_file_is_left_to_results(repo):
    from syseng import check
    findings = check.check(model.load(repo / "spec"))
    assert not [f for f in findings if f.code == "V002"]


def test_the_status_prints_for_people(repo, capsys):
    _add("--step", "unit", "--id", "//api:one_test", "--outcome", "fail")
    assert cli.main(["results", "status", "--all"]) == 1
    out = capsys.readouterr().out
    assert "FAILING SYS-V1" in out and "last tested in r1" in out and "not implemented" in out


def _record(repo):
    return json.loads(next((repo / ".syseng" / "results").rglob("*.json")).read_text())


def test_a_record_keeps_the_step_revision_time_and_outcomes(repo):
    _add("--step", "unit", "--id", "t", "--outcome", "pass", "--ran-at", "2026-01-02T03:04:00+00:00")
    r = _record(repo)
    assert (r["step"], r["revision"], r["when"], r["tests"]) == ("unit", "r1", "2026-01-02T03:04:00+00:00", {"t": "pass"})


def test_the_revision_defaults_to_version_controls_current_one(repo, capsys):
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True).stdout.strip()
    assert cli.main(["results", "add", "--step", "unit", "--id", "t", "--outcome", "pass"]) == 0
    assert _record(repo)["revision"] == head


def test_verdicts_given_one_at_a_time_share_a_step(repo, capsys):
    _add("--step", "review", "--id", "SYS-V1", "--outcome", "fail")
    _add("--step", "review", "--id", "SYS-V3", "--outcome", "pass")
    assert _status(capsys)[0] == 1


def test_when_tests_ran_decides_not_when_they_were_added(repo, capsys):
    _add("--step", "new", "--id", "//api:one_test", "--outcome", "fail", "--ran-at", "2026-02-01T00:00:00+00:00")
    _add("--step", "old", "--id", "//api:one_test", "--outcome", "pass", "--ran-at", "2026-01-01T00:00:00+00:00")
    assert _by_id(_status(capsys)[1])["SYS-V1"]["status"] == results.FAILING


def test_a_bad_ran_at_is_refused(repo, capsys):
    assert _add("--step", "u", "--id", "t", "--outcome", "pass", "--ran-at", "yesterday") == 1


def test_a_file_that_cannot_be_imported_fails_its_linked_tests(repo, capsys):
    (repo / "tests").mkdir()
    (repo / "tests" / "test_b.py").write_text("")
    path = repo / "spec" / "elements" / "SYS" / "verification.yaml"
    path.write_text(path.read_text().replace('"//api:one_test"', '"tests/test_b.py::test_x"'))
    good = '<testsuite><testcase classname="tests.test_b" name="test_x"/></testsuite>'
    bad = '<testsuite><testcase classname="" name="tests.test_b"><error/></testcase></testsuite>'
    (repo / "good.xml").write_text(good)
    (repo / "bad.xml").write_text(bad)
    _add("good.xml", "--format", "pytest-junit", "--step", "unit", revision="r1")
    _add("bad.xml", "--format", "pytest-junit", "--step", "unit", revision="r2")
    assert _by_id(_status(capsys)[1])["SYS-V1"]["status"] == results.FAILING
    _add("good.xml", "--format", "pytest-junit", "--step", "unit", revision="r3")
    assert _by_id(_status(capsys)[1])["SYS-V1"]["status"] == results.PASSING


def test_googletests_notrun_counts_as_skipped(tmp_path):
    path = tmp_path / "r.xml"
    path.write_text('<testsuite><testcase classname="S" name="T" status="notrun"/></testsuite>')
    assert readers.read("junit", path, tmp_path) == {"S.T": "skip"}


def test_a_namespaced_report_is_read(tmp_path):
    path = tmp_path / "r.xml"
    path.write_text('<testsuite xmlns="urn:x"><testcase name="T"><failure/></testcase></testsuite>')
    assert readers.read("junit", path, tmp_path) == {"T": "fail"}


def test_an_empty_report_records_nothing_and_keeps_what_was_there(repo, capsys):
    _add("--step", "unit", "--id", "//api:one_test", "--outcome", "fail")
    (repo / "empty.xml").write_text("<testsuites/>")
    assert _add("empty.xml", "--step", "unit") == 1
    assert "nothing was recorded" in capsys.readouterr().out
    assert _status(capsys)[0] == 1


def _rollup_spec(repo, verifies="[SYS-1]"):
    path = repo / "spec" / "elements" / "SYS" / "requirements.yaml"
    path.write_text(path.read_text() + "- id: SYS-3\n  kind: system\n  text: The tool shall do three.\n"
                    "  serves: [NEED-1]\n  traces_to: SYS-1\n  basis: derived\n  why: w\n")
    path = repo / "spec" / "elements" / "SYS" / "verification.yaml"
    path.write_text(path.read_text().replace("verifies: [SYS-1]", "verifies: [SYS-3]") + textwrap.dedent(f"""\
        - id: SYS-V4
          verifies: {verifies}
          method: analysis
          technique: roll-up
          description: By its children.
        """))


def test_a_roll_up_follows_its_children(repo, capsys):
    _rollup_spec(repo)
    assert _by_id(_status(capsys)[1])["SYS-V4"]["status"] == results.NOT_RUN
    _add("--step", "u", "--id", "//api:one_test", "--outcome", "pass")
    row = _by_id(_status(capsys)[1])["SYS-V4"]
    assert row["status"] == results.PASSING and row["last_tested"] == "r1"
    _add("--step", "u", "--id", "//api:one_test", "--outcome", "fail", revision="r2")
    row = _by_id(_status(capsys)[1])["SYS-V4"]
    assert row["status"] == results.FAILING and row["failed"] == ["SYS-V1"]


def test_a_chain_of_roll_ups_follows_the_leaves(repo, capsys):
    _rollup_spec(repo)
    path = repo / "spec" / "elements" / "SYS" / "requirements.yaml"
    path.write_text(path.read_text() + "- id: SYS-4\n  kind: system\n  text: The tool shall do four.\n"
                    "  serves: [NEED-1]\n  traces_to: SYS-3\n  basis: derived\n  why: w\n")
    path = repo / "spec" / "elements" / "SYS" / "verification.yaml"
    path.write_text(path.read_text().replace("verifies: [SYS-3]", "verifies: [SYS-4]") + textwrap.dedent("""\
        - id: SYS-V5
          verifies: [SYS-3]
          method: analysis
          technique: roll-up
          description: By its children.
        """))
    _add("--step", "u", "--id", "//api:one_test", "--outcome", "pass")
    items = _by_id(_status(capsys)[1])
    assert items["SYS-V5"]["status"] == items["SYS-V4"]["status"] == results.PASSING
    _add("--step", "u", "--id", "//api:one_test", "--outcome", "fail", revision="r2")
    assert _by_id(_status(capsys)[1])["SYS-V4"]["status"] == results.FAILING


def test_a_roll_up_with_an_unverified_child_is_not_passing(repo, capsys):
    _rollup_spec(repo)
    path = repo / "spec" / "elements" / "SYS" / "verification.yaml"
    path.write_text(path.read_text().replace("verifies: [SYS-3]", "verifies: [SYS-2]"))
    assert _by_id(_status(capsys)[1])["SYS-V4"]["status"] == results.NOT_RUN


def test_a_verdict_cannot_override_a_roll_ups_failing_child(repo, capsys):
    _rollup_spec(repo)
    _add("--step", "u", "--id", "//api:one_test", "--outcome", "fail")
    _add("--step", "v", "--id", "SYS-V4", "--outcome", "pass")
    assert _by_id(_status(capsys)[1])["SYS-V4"]["status"] == results.FAILING


def test_a_roll_up_over_a_parent_and_its_child_terminates(repo, capsys):
    _rollup_spec(repo, "[SYS-1, SYS-3]")
    assert _status(capsys)[0] == 0


def test_identifiers_from_junit_match_links_of_either_form(repo, capsys):
    path = repo / "spec" / "elements" / "SYS" / "verification.yaml"
    path.write_text(path.read_text().replace('"//api:one_test"', '"Suite.Test"')
                    .replace('"//api:two_test", "infra/apply"', '"src/a.cc::Other.Case"'))
    from syseng import testlinks
    assert not testlinks.names_file("Suite.Test") and not testlinks.names_file("tests.test_a.test_one")
    (repo / "r.xml").write_text('<testsuite><testcase classname="Suite" name="Test"/>'
                                '<testcase classname="Other" name="Case"/></testsuite>')
    _add("r.xml", "--step", "unit")
    data = _status(capsys)[1]
    assert _by_id(data)["SYS-V1"]["status"] == _by_id(data)["SYS-V2"]["status"] == results.PASSING
    assert data["aws"]["unlinked"] == []


def test_parametrized_results_match_a_bare_link(repo, capsys):
    (repo / "a.jsonl").write_text('{"id": "//api:one_test[1]", "outcome": "pass"}\n'
                                  '{"id": "//api:one_test[2]", "outcome": "fail"}\n')
    _add("a.jsonl", "--format", "jsonl", "--step", "u")
    data = _status(capsys)[1]
    assert _by_id(data)["SYS-V1"]["status"] == results.FAILING and data["aws"]["unlinked"] == []


def test_skipped_tests_nothing_links_are_listed_in_full(repo, capsys):
    (repo / "a.jsonl").write_text("".join(f'{{"id": "t{n}", "outcome": "skip"}}\n' for n in range(10)))
    _add("a.jsonl", "--format", "jsonl", "--step", "u")
    capsys.readouterr()
    cli.main(["results", "status"])
    out = capsys.readouterr().out
    assert "10 tests" in out and "t0" in out and "t9" in out


def test_a_corrupt_results_file_is_skipped_with_a_warning(repo, capsys):
    _add("--step", "unit", "--id", "t", "--outcome", "pass")
    next((repo / ".syseng" / "results").rglob("*.json")).write_text("{nope")
    assert cli.main(["results", "status"]) == 0
    assert "can't be read" in capsys.readouterr().err


def test_a_binary_report_is_named(repo, capsys):
    (repo / "a.jsonl").write_bytes(b"\xff\xfe\x00")
    assert _add("a.jsonl", "--format", "jsonl", "--step", "u") == 1
    assert "can't read" in capsys.readouterr().out


def test_an_unknown_backend_is_reported_without_a_traceback(repo, capsys):
    settings = repo / "spec" / "toolkit.yaml"
    settings.write_text(settings.read_text() + "version_control: piper\n")
    assert cli.main(["results", "add", "--step", "u", "--id", "t", "--outcome", "pass"]) == 1
    assert "no version-control backend" in capsys.readouterr().out


def _lock(repo, *ids):
    from syseng import review
    spec = model.load(repo / "spec")
    (repo / "spec" / "locks.yaml").write_text(yaml.safe_dump([
        {"id": i, "by": "Ada <ada@example.com>", "when": "2026-01-01", "via": "chat", "count": 1,
         "fingerprint": review.current_fingerprint(spec, i)} for i in ids]))


def test_a_failure_shows_what_it_checks_and_the_locked_items_above_it(repo, capsys):
    _lock(repo, "NEED-1")
    _add("--step", "u", "--id", "//api:one_test", "--outcome", "fail")
    capsys.readouterr()
    assert cli.main(["results", "status"]) == 1
    out = capsys.readouterr().out
    assert "checks: One." in out
    assert "verifies SYS-1 (derived): The tool shall do one." in out
    assert "above: NEED-1 (explicit): The engineer needs it." in out
    assert "that's a conflict to raise" in out


def test_items_no_person_stated_stay_out_unless_asked_for(repo, capsys):
    _add("--step", "u", "--id", "//api:one_test", "--outcome", "fail")
    capsys.readouterr()
    cli.main(["results", "status"])
    out = capsys.readouterr().out
    assert "above: NEED-1" not in out and "1 more above" in out and "A person's direction" not in out
    cli.main(["results", "status", "--full-trace"])
    assert "above: NEED-1 (derived)" in capsys.readouterr().out


def test_each_text_is_shown_once_however_many_failures_reach_it(repo, capsys):
    _lock(repo, "NEED-1")
    _add("--step", "u", "--id", "//api:one_test", "--outcome", "fail")
    _add("--step", "v", "--id", "//api:two_test", "--outcome", "fail")
    capsys.readouterr()
    cli.main(["results", "status"])
    out = capsys.readouterr().out
    assert out.count("The engineer needs it.") == 1 and "NEED-1 (explicit), shown above" in out
    _, data = _status(capsys)
    assert set(data["aws"]["context"]) == {"SYS-1", "SYS-2", "NEED-1"}
    assert data["aws"]["failing"][0]["trace"][0]["above"] == ["NEED-1"]


def test_a_need_marked_derived_does_not_count_as_a_persons_word(repo):
    from syseng import levels
    assert levels.level_of(model.load(repo / "spec"), "NEED-1").level == levels.DERIVED


def test_the_report_says_whether_results_are_recorded(repo, capsys):
    from syseng import page
    assert _status(capsys)[1]["aws"]["recorded"] is False
    _add("--step", "u", "--id", "t", "--outcome", "pass")
    assert _status(capsys)[1]["aws"]["recorded"] is True
    assert "No test results are recorded for" in (page.WEB / "review.js").read_text()
