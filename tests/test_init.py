"""`spec init` sets a repository up in one step (SYS-5, CLI-9) and re-runs cleanly (CLI-10)."""

import json
import os
import subprocess

import pytest
from pathlib import Path

from syseng import check, cli, init, model


@pytest.fixture
def repo(tmp_path):
    path = tmp_path / "repo"
    path.mkdir()
    (path / "pyproject.toml").write_text("[project]\nname = 'demo'\n")
    return path


def _statuses(steps):
    return {s.path: s.status for s in steps}


def test_init_sets_up_an_empty_repository(repo, machine):
    init.run(repo, ["claude-code"])
    spec = model.load(repo / "spec")
    assert [f for f in check.check(spec) if f.severity == "error"] == []
    assert spec.config["implementations"][0]["language"] == "python"
    home = Path.home()
    assert (home / ".claude/skills/syseng").resolve() == init.SKILL                 # the machine's toolkit
    assert (home / ".claude/agents/spec-reasoning-check.md").is_symlink()
    assert not (repo / ".claude/skills").exists() and not (repo / ".agents").exists()   # no copies here
    assert init.installed_harnesses(repo) == ["claude-code"]
    assert os.access(repo / ".syseng/hook", os.X_OK) and not (repo / ".syseng/spec").exists()
    hooks = json.loads((repo / ".claude/settings.json").read_text())["hooks"]
    assert set(hooks) == {"PreToolUse", "Stop", "UserPromptSubmit"}


def test_init_says_when_spec_is_not_on_the_path(repo, tmp_path, monkeypatch):
    (tmp_path / "empty").mkdir()
    monkeypatch.setenv("PATH", str(tmp_path / "empty"))
    notes = [s for s in init.run(repo, ["claude-code"]) if s.status == "note"]
    assert notes and "pipx install" in notes[0].note


def test_init_removes_the_launcher_earlier_setups_wrote(repo, machine):
    old = repo / ".syseng/spec"
    old.parent.mkdir()
    old.write_text("#!/bin/sh\n# Runs the spec toolkit for this repository. Written by `spec init`; commit it.\n")
    assert _statuses(init.run(repo, ["claude-code"]))[".syseng/spec"] == "removed"
    assert not old.exists()


def test_init_again_changes_nothing(repo, machine):
    init.run(repo, ["claude-code"])
    again = init.run(repo, ["claude-code"])
    assert {s.status for s in again} <= {"unchanged", "kept"}


def test_init_keeps_other_settings_and_hooks(repo, machine):
    settings = repo / ".claude/settings.json"
    settings.parent.mkdir()
    theirs = {"type": "command", "command": "./lint.sh"}
    settings.write_text(json.dumps({"model": "opus", "hooks": {"PreToolUse": [{"matcher": "Bash", "hooks": [theirs]}]}}))
    init.run(repo, ["claude-code"])
    init.run(repo, ["claude-code"])
    data = json.loads(settings.read_text())
    assert data["model"] == "opus"
    pre = data["hooks"]["PreToolUse"]
    assert pre[0] == {"matcher": "Bash", "hooks": [theirs]}
    ours = [h["command"] for g in pre for h in g["hooks"] if ".syseng/hook" in h["command"]]
    assert sorted(c.split()[-1] for c in ours) == ["pre-tool", "read-guard"]   # each once, after two runs


def test_init_refuses_unreadable_settings(repo, machine):
    settings = repo / ".claude/settings.json"
    settings.parent.mkdir()
    settings.write_text("{not json")
    with pytest.raises(init.InitError, match="settings.json"):
        init.run(repo, ["claude-code"])
    assert settings.read_text() == "{not json"


def test_init_removes_skill_files_the_skill_no_longer_has(repo, machine):
    init.run(repo, ["antigravity"])
    stale = repo / ".agents/skills/syseng/references/old.md"
    stale.write_text("gone")
    assert _statuses(init.run(repo, ["antigravity"]))[".agents/skills/syseng/references/old.md"] == "removed"
    assert not stale.exists()


def test_check_reports_installed_files_that_drifted(repo, machine):
    init.run(repo, ["claude-code"])
    (repo / ".syseng/hook").write_text("edited")
    steps = init.run(repo, ["claude-code"], check_only=True)
    assert _statuses(steps)[".syseng/hook"] == "differs"
    assert (repo / ".syseng/hook").read_text() == "edited"                     # check writes nothing


def test_antigravity_gets_the_skill_without_claude_code_glue(repo, machine):
    init.run(repo, ["antigravity"])
    assert (repo / ".agents/skills/syseng/SKILL.md").exists()
    assert not (repo / ".claude").exists() and not (repo / ".syseng/hook").exists()


def test_existing_spec_is_left_alone(spec, machine):
    root = spec.write()
    before = (root / "elements/SYS/element.yaml").read_text()
    steps = init.run(root.parent, ["claude-code"])
    assert _statuses(steps)["spec/"] == "kept"
    assert (root / "elements/SYS/element.yaml").read_text() == before


def test_hermes_gets_its_link_and_the_note_that_no_hooks_run(repo, machine):
    steps = init.run(repo, ["hermes"])
    assert any(s.status == "note" and s.path == "~/.hermes" for s in steps)      # no Hermes here yet
    (Path.home() / ".hermes").mkdir()
    init.run(repo, ["hermes"])
    assert (Path.home() / ".hermes/skills/syseng").resolve() == init.SKILL
    text = (repo / "AGENTS.md").read_text()
    assert "no toolkit hooks run" in text and "Spec guard" not in text
    assert not (repo / ".claude").exists() and not (repo / ".agents").exists()


def test_the_instructions_say_what_each_harness_hooks_do(repo, machine):
    init.run(repo, ["claude-code", "hermes"])
    text = (repo / "AGENTS.md").read_text()
    for hook in ("Spec guard", "Done gate", "Lock reader"):
        assert hook in text
    assert "In other harnesses no toolkit hooks run" in text


def test_older_per_repository_installs_move_to_the_machine(repo, machine):
    for rel in (".claude/skills/syseng", ".agents/skills/syseng"):
        (repo / rel).mkdir(parents=True)
        (repo / rel / "SKILL.md").write_text("---\nname: syseng\n---\nold copy\n")
    (repo / ".claude/agents").mkdir()
    (repo / ".claude/agents/spec-auditor.md").write_text("---\nname: spec-auditor\n---\n")
    (repo / ".agents/skills/benchmarking").mkdir()                             # someone else's skill stays
    steps = _statuses(init.run(repo, ["claude-code"]))
    for rel in (".claude/skills/syseng", ".agents/skills/syseng", ".claude/agents/spec-auditor.md"):
        assert steps[rel] == "removed" and not (repo / rel).exists()
    assert (repo / ".agents/skills/benchmarking").is_dir() and not (repo / ".claude/skills").exists()
    assert steps["~/.claude/skills/syseng"] == "created"
    assert _statuses(init.run(repo, init.installed_harnesses(repo)))["~/.claude/skills/syseng"] == "unchanged"


def test_skills_and_agents_of_your_own_are_left_alone(repo, machine):
    own = Path.home() / ".claude/skills/syseng"
    own.mkdir(parents=True)
    (own / "SKILL.md").write_text("mine")
    steps = init.run(repo, ["claude-code"])
    assert any(s.status == "note" and s.path == "~/.claude/skills/syseng" for s in steps)
    assert (own / "SKILL.md").read_text() == "mine"


def test_a_plain_rerun_refreshes_every_installed_harness(repo, machine):
    init.run(repo, ["claude-code", "hermes"])
    (repo / ".syseng/hook").write_text("stale")
    assert cli.main(["init", "--repo", str(repo)]) == 0
    assert all(s.status != "differs" for s in init.run(repo, ["claude-code", "hermes"], check_only=True))


def test_init_points_every_session_at_the_skill(repo, machine):
    (repo / "AGENTS.md").write_text("# Project rules\n\nBe kind to the build.\n")
    init.run(repo, ["claude-code"])
    text = (repo / "AGENTS.md").read_text()
    assert text.startswith("# Project rules\n\nBe kind to the build.\n\n<!-- syseng:")
    assert "follow the `syseng` skill" in text and "`spec edit`" in text
    init.run(repo, ["claude-code"])
    assert (repo / "AGENTS.md").read_text() == text                  # a re-run changes nothing


def test_init_leaves_a_claude_md_that_includes_agents_md(repo, machine):
    (repo / "AGENTS.md").write_text("rules\n")
    (repo / "CLAUDE.md").write_text("@AGENTS.md\n")
    init.run(repo, ["claude-code"])
    assert (repo / "CLAUDE.md").read_text() == "@AGENTS.md\n" and "syseng" in (repo / "AGENTS.md").read_text()


def test_init_can_leave_instruction_files_alone(repo, machine):
    init.run(repo, ["claude-code"], instructions=False)
    assert not (repo / "AGENTS.md").exists()
    assert not [s for s in init.run(repo, ["claude-code"], check_only=True) if s.status == "differs"]


def test_agents_may_run_the_everyday_commands_without_asking(repo, machine):
    init.run(repo, ["claude-code"])
    init.run(repo, ["claude-code"])
    allow = json.loads((repo / ".claude/settings.json").read_text())["permissions"]["allow"]
    assert "Bash(spec edit *)" in allow and "Bash(spec status *)" in allow
    assert not [r for r in allow if "approve" in r or "resolve" in r]   # those record the engineer's words
    assert len(allow) == len(set(allow))
