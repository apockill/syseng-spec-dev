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


def test_the_skill_is_installed_as_is():
    for path in SKILL_FILES + AGENT_FILES:
        assert "{{" not in path.read_text(), f"{path.name} still has a placeholder"
    for notes in (init.CLAUDE_NOTES, init.GENERIC_NOTES):
        assert "hooks" in notes.read_text()


def _whole_skill():
    return "\n".join(p.read_text() for p in SKILL_FILES)


def test_skill_teaches_locks_without_a_ritual():
    text = _whole_skill()
    assert "Locks belong to the engineer" in text and "never their exact words" in text
    assert "a general \"looks good\" locks nothing" in text


def test_skill_invites_agents_to_improve_it():
    text = (init.SKILL / "SKILL.md").read_text()
    assert "## Improving this skill" in text and "friction --workaround" in text


def test_every_command_the_skill_names_exists():
    named = set()
    for path in SKILL_FILES + AGENT_FILES:
        named |= set(re.findall(r"`spec ([a-z]+)", path.read_text()))
    assert named and named <= cli.commands(), named - cli.commands()


def test_reasoning_check_subagent_starts_clean_and_cannot_read_the_spec():
    meta = _frontmatter(init.ADAPTERS / "claude_code/agents/spec-reasoning-check.md")
    assert meta["omitClaudeMd"] is True
    assert {t.strip() for t in meta["tools"].split(",")} == {"Read", "Grep", "Glob"}
    reads = [g for e, m, a in init.HOOKS if a == "read-guard" for g in [m]]
    assert reads == ["Read|Grep|Glob|NotebookRead"]           # in settings, which every folder honors
    from syseng.adapters import hook
    assert meta["name"] == hook.READING_AGENT


def test_auditor_subagent_is_described():
    meta = _frontmatter(init.ADAPTERS / "claude_code/agents/spec-auditor.md")
    assert meta["name"] == "spec-auditor" and meta["description"]


def test_skill_teaches_the_approval_model():
    text = _whole_skill()
    assert "spec propose" in text and "most consequential first" in text          # AGENT-51
    assert "whose consequences reach the engineer" in text and "no substitute for your judgment" in text
    assert "which they keep on the page (or with `lock <ID>`)" in text                 # AGENT-52
    assert "Run `spec review`" in text and "spec feedback apply" in text and "spec feedback respond" in text  # AGENT-62, SYS-52
    assert "not just their \"yes\"" in text and "adds no claim they didn't make" in text  # AGENT-53, AGENT-54
    assert "Place each requirement under the system element it constrains" in text     # AGENT-55
    assert "add the request to them as intent" in text and "or restate one" in text     # AGENT-56, AGENT-50
    assert "record the lower level" in text and "Summarize, never quote" in text        # AGENT-63, SYS-35
    assert "with `basis: added`) for each feature a user would notice" in text          # AGENT-60
    assert "Look for conflicts" in text and "kind: conflict" in text                   # AGENT-61, CHANGE-17


# Progressive disclosure, after Anthropic's skill-authoring guidance (AGENT-65)
REFERENCES = sorted((init.SKILL / "references").glob("*.md"))


def test_skill_md_stays_short_and_routes_to_every_reference():
    text = (init.SKILL / "SKILL.md").read_text()
    assert len(text.splitlines()) < 500
    for ref in REFERENCES:
        assert f"references/{ref.name}" in text, f"SKILL.md doesn't route to {ref.name}"


@pytest.mark.parametrize("path", REFERENCES, ids=lambda p: p.name)
def test_references_are_one_level_deep_and_long_ones_have_contents(path):
    text = path.read_text()
    assert not re.search(r"\]\((?:references/)?[a-z-]+\.md\)", text), f"{path.name} links to another reference"
    if len(text.splitlines()) > 100:
        assert "## Contents" in text, f"{path.name} is over 100 lines with no contents"


@pytest.mark.parametrize("path", SKILL_FILES, ids=lambda p: p.name)
def test_examples_write_intent_in_block_style(path):
    assert not re.search(r"intent:\s*\{", path.read_text()), f"{path.name} shows a flow-style intent mapping"


def test_skill_teaches_the_onboarding_lessons_of_the_three_agent_trial():
    text = _whole_skill()
    assert "Never infer pronouns from a name" in text                                   # AGENT-66
    assert "Never set it yourself from memory" in text                                   # AGENT-67
    assert "A document isn't a statement" in text and "who wrote it" in text            # AGENT-68
    onboarding = (init.SKILL / "references" / "onboarding.md").read_text()
    assert "## 1. Preflight" in onboarding and "stop and ask the engineer" in onboarding  # ONBOARD-8
    assert "## 3. Altitude" in onboarding and "Constants stay out of requirements" in onboarding  # ONBOARD-9
    assert "Don't reword the requirement to match the code" in onboarding                # ONBOARD-10
    assert "Run every automated check" in onboarding and "options with costs" in onboarding  # ONBOARD-3, ONBOARD-12
    assert "isn't verification yet" in onboarding                                        # ONBOARD-11


def test_skill_puts_questions_for_the_engineer_on_a_rendered_page():           # AGENT-69
    text = _whole_skill()
    assert "goes on a rendered page" in text and "a reader with none of your context" in text
    assert "spec decide --replace" in text
