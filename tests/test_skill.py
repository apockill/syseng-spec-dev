"""The skill and the Claude Code subagents `spec init` installs (AGENT-42, AGENT-45, DR-38)."""

import re

import pytest
import yaml

from syseng import cli, init

SKILL_FILES = sorted(p for p in init.SKILL.rglob("*.md"))
AGENT_FILES = sorted((init.ADAPTERS / "claude_code" / "agents").glob("*.md"))


def _frontmatter(path):
    text = path.read_text()
    assert text.startswith("---\n"), f"{path.name} has no frontmatter"
    return yaml.safe_load(text.split("---\n")[1])


def test_skill_frontmatter_follows_the_agent_skills_format():
    meta = _frontmatter(init.SKILL / "SKILL.md")
    assert re.fullmatch(r"[a-z0-9-]{1,64}", meta["name"])
    assert 0 < len(meta["description"]) <= 1024


@pytest.mark.parametrize("path", SKILL_FILES, ids=lambda p: p.name)
def test_skill_names_no_particular_harness(path):
    text = path.read_text()
    for word in ("Claude Code", "Antigravity", "Codex", "AskUserQuestion", "CLAUDE.md", "subagent_type"):
        assert word not in text, f"{path.name} mentions {word}"
    assert not re.search(r"\bnix\b", text, re.I), f"{path.name} mentions Nix"


def test_skill_leaves_one_slot_for_the_harness_notes():
    assert (init.SKILL / "SKILL.md").read_text().count("{{HARNESS_NOTES}}") == 1
    for notes in [init.GENERIC_NOTES, *init.HARNESS_NOTES.values()]:
        assert notes.read_text().startswith("## What this harness does for you")


def test_skill_tells_agents_to_give_the_exact_approval_line():
    assert "give them the exact line that records it" in (init.SKILL / "SKILL.md").read_text()


def test_skill_invites_agents_to_improve_it():
    text = (init.SKILL / "SKILL.md").read_text()
    assert "## Improving this skill" in text and "friction --workaround" in text


def test_every_command_the_skill_names_exists():
    named = set()
    for path in SKILL_FILES + AGENT_FILES:
        named |= set(re.findall(r"\{\{SPEC\}\} ([a-z]+)", path.read_text()))
    assert named and named <= cli.commands(), named - cli.commands()


def test_reasoning_check_subagent_starts_clean_and_cannot_read_the_spec():
    meta = _frontmatter(init.ADAPTERS / "claude_code/agents/spec-reasoning-check.md")
    assert meta["omitClaudeMd"] is True
    assert {t.strip() for t in meta["tools"].split(",")} == {"Read", "Grep", "Glob"}
    commands = [h["command"] for g in meta["hooks"]["PreToolUse"] for h in g["hooks"]]
    assert any(".syseng/hook read-guard" in c for c in commands)


def test_auditor_subagent_is_described():
    meta = _frontmatter(init.ADAPTERS / "claude_code/agents/spec-auditor.md")
    assert meta["name"] == "spec-auditor" and meta["description"]


def test_skill_teaches_the_approval_model():
    text = (init.SKILL / "SKILL.md").read_text()
    assert "{{SPEC}} propose" in text and "most consequential first" in text          # AGENT-51
    assert "the line that keeps it" in text                                            # AGENT-52
    assert "not just their \"yes\"" in text and "says only what was being discussed" in text  # AGENT-53, AGENT-54
    assert "Place each requirement under the system element it constrains" in text     # AGENT-55
    assert "add the engineer's words to them" in text and "--via <chat|menu|restated>" in text  # AGENT-56, AGENT-50
