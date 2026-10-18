"""This repository passes its own checker (SYS-2), and the CLI works on it end to end."""

from pathlib import Path

from syseng import check, cli, init, model

REPO_SPEC = Path(__file__).resolve().parents[1] / "spec"


def test_repository_spec_passes_its_own_checker():
    findings = check.check(model.load(REPO_SPEC))
    errors = [f for f in findings if f.severity == "error"]
    assert errors == [], check.format_findings(errors, REPO_SPEC)


def test_repository_runs_the_current_skill_and_hooks():
    repo = REPO_SPEC.parent
    harnesses = init.installed_harnesses(repo)
    stale = [s.path for s in init.run(repo, harnesses, check_only=True) if s.status == "differs"]
    assert harnesses and stale == [], f"run `bin/spec init` to refresh: {stale}"


def test_show_prints_the_trace_up_to_the_needs(capsys):
    assert cli.main(["--spec", str(REPO_SPEC), "show", "MODEL-1"]) == 0
    out = capsys.readouterr().out
    assert "MODEL-1" in out and "↑ SYS-6" in out and "↑ NEED-1" in out


def test_check_exit_code_reflects_errors(spec):
    root = spec.write()
    assert cli.main(["--spec", str(root), "check"]) == 0
    spec.files["elements/CORE/requirements.yaml"][0]["text"] = "The core stamps widgets."
    spec.write()
    assert cli.main(["--spec", str(root), "check"]) == 1


def test_todo_lists_unapproved_items(spec, capsys):
    root = spec.write()
    cli.main(["--spec", str(root), "check", "--todo"])
    out = capsys.readouterr().out
    assert "todo[A003] CORE-1 is unapproved" in out
