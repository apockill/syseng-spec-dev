"""`spec init` sets a repository up in one step (SYS-5, CLI-9) and re-runs cleanly (CLI-10)."""

import json
import os
import subprocess

import pytest

from syseng import check, cli, init, model


@pytest.fixture
def machine(tmp_path, monkeypatch):
    """This machine's config directory, kept inside the test's temporary directory."""
    xdg = tmp_path / "xdg"
    monkeypatch.setenv("XDG_CONFIG_HOME", str(xdg))
    return xdg


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
    skill = (repo / ".claude/skills/syseng/SKILL.md").read_text()
    assert "{{SPEC}}" not in skill and ".syseng/spec edit" in skill
    assert (repo / ".claude/skills/syseng/references/rules.md").exists()
    assert os.access(repo / ".syseng/hook", os.X_OK) and os.access(repo / ".syseng/spec", os.X_OK)
    hooks = json.loads((repo / ".claude/settings.json").read_text())["hooks"]
    assert set(hooks) == {"PreToolUse", "Stop", "UserPromptSubmit"}
    assert (repo / ".claude/agents/spec-reasoning-check.md").exists()
    assert os.access(machine / "syseng/launcher", os.X_OK)


def test_launcher_runs_the_toolkit_from_the_repository(repo, machine):
    init.run(repo, ["claude-code"])
    out = subprocess.run([str(repo / ".syseng/spec"), "check"], cwd=repo, capture_output=True, text=True)
    assert out.returncode == 0 and "spec check: 0 errors" in out.stdout


def test_launcher_explains_a_machine_without_the_toolkit(repo, machine, tmp_path):
    init.run(repo, ["claude-code"])
    env = {**os.environ, "XDG_CONFIG_HOME": str(tmp_path / "elsewhere")}
    out = subprocess.run([str(repo / ".syseng/spec"), "check"], cwd=repo, capture_output=True, text=True, env=env)
    assert out.returncode == 127 and "not set up on this machine" in out.stderr


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
    assert sum(".syseng/hook" in h["command"] for g in pre for h in g["hooks"]) == 1


def test_init_refuses_unreadable_settings(repo, machine):
    settings = repo / ".claude/settings.json"
    settings.parent.mkdir()
    settings.write_text("{not json")
    with pytest.raises(init.InitError, match="settings.json"):
        init.run(repo, ["claude-code"])
    assert settings.read_text() == "{not json"


def test_init_removes_skill_files_the_skill_no_longer_has(repo, machine):
    init.run(repo, ["claude-code"])
    stale = repo / ".claude/skills/syseng/references/old.md"
    stale.write_text("gone")
    assert _statuses(init.run(repo, ["claude-code"]))[".claude/skills/syseng/references/old.md"] == "removed"
    assert not stale.exists()


def test_check_reports_installed_files_that_drifted(repo, machine):
    init.run(repo, ["claude-code"])
    (repo / ".claude/skills/syseng/SKILL.md").write_text("edited")
    steps = init.run(repo, ["claude-code"], check_only=True)
    assert _statuses(steps)[".claude/skills/syseng/SKILL.md"] == "differs"
    assert (repo / ".claude/skills/syseng/SKILL.md").read_text() == "edited"   # check writes nothing


def test_machine_launcher_is_kept_unless_replaced(repo, machine):
    init.run(repo, ["claude-code"])
    launcher = machine / "syseng/launcher"
    first = launcher.read_text()
    init.run(repo, ["claude-code"])
    assert launcher.read_text() == first
    init.run(repo, ["claude-code"], launcher="/opt/py/bin/python3 -m syseng")
    assert 'exec /opt/py/bin/python3 -m syseng "$@"' in launcher.read_text()


def test_default_launcher_uses_plain_python(machine):
    command = init.default_launcher()
    assert "-m syseng" in command and "nix" not in command.replace(init.sys.executable, "")


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


def test_hermes_gets_the_cross_tool_skill_without_hooks(repo, machine):
    init.run(repo, ["hermes"])
    skill = (repo / ".agents/skills/syseng/SKILL.md").read_text()
    assert "No toolkit hooks run in this harness" in skill and "{{HARNESS_NOTES}}" not in skill
    assert not (repo / ".claude").exists() and not (repo / ".syseng/hook").exists()
    assert init.installed_harnesses(repo) == ["hermes"]


def test_each_skill_copy_says_what_its_harness_hooks_do(repo, machine):
    init.run(repo, ["claude-code", "hermes"])
    claude = (repo / ".claude/skills/syseng/SKILL.md").read_text()
    for hook in ("Spec guard", "Done gate", "Approval reader"):
        assert hook in claude
    assert "Spec guard" not in (repo / ".agents/skills/syseng/SKILL.md").read_text()


def test_a_plain_rerun_refreshes_every_installed_harness(repo, machine):
    init.run(repo, ["claude-code", "hermes"])
    for copy in (".claude/skills/syseng/SKILL.md", ".agents/skills/syseng/SKILL.md"):
        (repo / copy).write_text("stale")
    assert cli.main(["init", "--repo", str(repo)]) == 0
    assert all(s.status != "differs" for s in init.run(repo, ["claude-code", "hermes"], check_only=True))
