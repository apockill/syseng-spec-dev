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
    assert "## Improving this skill" in text and "references/reporting-problems.md" in text


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
    assert "Say where intent came from" in text and "source kind, path and author" in text  # AGENT-68
    onboarding = (init.SKILL / "references" / "onboarding.md").read_text()
    depth = (init.SKILL / "references" / "requirement-depth.md").read_text()
    assert "## 1. Preflight" in onboarding and "raise it as the first open decision" in onboarding  # ONBOARD-8
    assert "One requirement per feature" in text and "Most values end here" in depth      # ONBOARD-9
    assert "Never reword a requirement, and never narrow a safety rule" in depth          # ONBOARD-10
    assert "Run every automated check" in onboarding and "options with costs" in onboarding  # ONBOARD-3, ONBOARD-12
    assert "isn't verification yet" in onboarding                                        # ONBOARD-11


def test_skill_puts_questions_for_the_engineer_on_a_rendered_page():           # AGENT-69
    text = _whole_skill()
    assert "goes on a rendered page" in text and "a reader with none of your context" in text
    assert "spec decide --replace" in text


def test_skill_teaches_how_deep_to_write_requirements():                                # AGENT-70, AGENT-71
    skill = (init.SKILL / "SKILL.md").read_text()
    depth = (init.SKILL / "references" / "requirement-depth.md").read_text()
    assert "**Depth follows intent.**" in skill and "as deep as they went" in skill
    assert "Count features, not effects" in skill and "the list of its standard names and values" in skill
    assert "ask instead of picking" in skill and "never restated in an element" in skill
    for part in ("## A. What counts as a noticeable feature", "## B. Where a value goes", "## C. Requirements you infer",
                 "## D. Code that falls short", "## E. Intent read from documents", "## F. Splitting a big element"):
        assert part in depth


def _depth_rule(n):
    skill = (init.SKILL / "SKILL.md").read_text()
    section = skill[skill.index("## How deep to write requirements"):skill.index("## Editing the spec")]
    return next(l for l in section.splitlines() if l.startswith(f"{n}. "))


def test_requirements_name_values_only_at_their_level_with_a_decision_record():         # AGENT-82, AGENT-83
    skill = (init.SKILL / "SKILL.md").read_text()
    depth = (init.SKILL / "references" / "requirement-depth.md").read_text()
    rule3 = _depth_rule(3)
    assert "**What's needed, at its level.**" in rule3 and "Needs and system requirements are solution-free" in rule3
    assert "only as a constraint the engineer imposed" in rule3
    assert "sits at the level where that choice applies and a decision record at that level or above gives the reason" in rule3
    assert "Otherwise the value goes in the verification item" in rule3 and "as prescriptive as its test" in rule3
    assert "interfaces included" not in skill + depth                    # the earlier, stricter rule is gone
    assert "**Environment-neutral.**" in skill and "a need's context may give example deployments" in skill
    part_b = depth[depth.index("## B."):depth.index("## C.")]
    assert "your what is my how" in part_b and "A choice made at one level is a legitimate what for the level below" in part_b
    assert "allow W009 on it citing the record" in part_b and "Needs and requirements, at every level, name no host" in part_b
    rule3 = next(l for l in part_b.splitlines() if l.startswith("3. "))
    assert "command and flag names" not in rule3.split("→")[0].lower()        # a flag a person types isn't an interface
    assert "state the capability" in rule3 and "at the lowest level" in rule3
    examples = depth[depth.index("## G."):]
    assert "socket named app.sock" in examples and "a decision record listing the app interface's standard names" in examples
    assert "The host's operating system, the proxy and the domain appear in no need or requirement" in examples
    w009 = (init.SKILL / "references" / "rules.md").read_text().split('<a id="w009">')[1].split("<a id=")[0]
    assert "at the lowest level where that choice applies" in w009 and "allow W009 on that item" in w009
    assert "named consumer" not in skill + depth


def test_skill_gives_the_engineers_test_for_every_requirement():                         # AGENT-85
    test = ("I should be able to look at any requirement, and with a little bit of context, agree 'yes this is a "
            "feature/something/an intent/etc that should exist/that I agree with' without also having to wonder if I "
            "also necessarily agree with the implementation details.")
    skill = (init.SKILL / "SKILL.md").read_text()
    rule6 = _depth_rule(6)
    assert "**The engineer's test.**" in rule6 and "Before handing over" in rule6 and test in rule6
    assert "Rewrite each that fails" in rule6
    assert test in (init.SKILL / "references" / "requirement-depth.md").read_text()
    onboarding = (init.SKILL / "references" / "onboarding.md").read_text()
    assert "7. Every requirement read against the engineer's test" in onboarding


def test_long_requirements_become_a_parent_and_children():                                # AGENT-86
    skill = (init.SKILL / "SKILL.md").read_text()
    rule5 = _depth_rule(5)
    assert "Write a parent's intent before its children" in rule5
    assert 'joins two behaviours with "and", "or" or ";"' in rule5 and "A parent with one child is suspect" in rule5
    depth = (init.SKILL / "references" / "requirement-depth.md").read_text()
    part_f = depth[depth.index("## F."):depth.index("## G.")]
    assert "A requirement is one thought" in part_f and "Write the parent first" in part_f
    assert "merge them" in part_f and "find it" in part_f
    assert "one child per outcome" in depth                              # the exit-code worked example


def test_verification_prefers_the_strongest_check_that_can_work():                        # AGENT-87
    skill = (init.SKILL / "SKILL.md").read_text()
    rule7 = _depth_rule(7)
    assert "automated test or static check first, then a reasoning check, then manual" in rule7
    assert "says why the stronger one can't work" in rule7
    writing = (init.SKILL / "references" / "writing-requirements.md").read_text()
    assert "Choose the strongest check that can work" in writing and "a linter over the code or the spec" in writing
    assert "says why the stronger one can't work" in writing


def test_every_change_that_alters_the_spec_ends_with_proposals():
    step = next(l for l in (init.SKILL / "SKILL.md").read_text().splitlines() if l.startswith("8. **Hand over**"))
    assert "ranked most important first" in step and "stop when their time runs out" in step
    locks = (init.SKILL / "references" / "review-and-locks.md").read_text()
    part = locks[locks.index("## Proposing items to lock"):]
    assert "in every change that alters the spec, not only onboarding" in part
    for kind in ("items you inferred", "exact name or value", "reworded the engineer's words into", "others build on"):
        assert kind in part
    assert "Group them by an honest reason" in part and "most important group first" in part
    assert "the order matters more than the count" in part and "three to eight" not in part   # no fixed number


def test_problem_reports_need_consent_general_terms_and_no_solution():
    text = (init.SKILL / "references" / "reporting-problems.md").read_text()
    for phrase in ("don't propose a solution", "repository is public", "ask whether to send it", "Only if they agree",
                   "full text", "worked around", "Rewrite everything in general terms"):
        assert phrase in text
    assert "reporting-problems.md" in (init.SKILL / "SKILL.md").read_text()


def test_agents_ask_for_a_reader_before_writing_their_own():
    text = (init.SKILL / "references" / "test-results.md").read_text()
    assert "offer to ask for one with a problem report" in text and "before writing a conversion of your own" in text


def test_every_pull_request_gets_a_review_page_against_its_base():
    text = (init.SKILL / "references" / "review-and-locks.md").read_text()
    assert "Every pull request that changes the spec gets its own page" in text
    assert "`spec review --against <its base branch>`" in text and "linked at the top of its description" in text


def test_handover_records_results_first():
    text = (init.SKILL / "references" / "review-and-locks.md").read_text()
    assert text.index("record their results first") < text.index("Run `spec review`")


def test_linking_tests_is_guided_link_first_add_last():
    text = (init.SKILL / "references" / "writing-requirements.md").read_text()
    assert "Link first, add last" in text and "Never add a requirement just to give a test a home" in text
    assert "link every test you add" in (init.SKILL / "SKILL.md").read_text()


def test_the_hand_over_step_says_to_offer_a_problem_report():
    step = next(l for l in (init.SKILL / "SKILL.md").read_text().splitlines() if l.startswith("8. **Hand over**"))
    assert "offer to report it" in step and "references/reporting-problems.md" in step


def test_the_schema_reference_is_generated_from_the_schema():
    from syseng import schema
    text = (init.SKILL / "references" / "schema.md").read_text()
    start = text.index("-->\n", text.index("<!-- generated by `spec schema`")) + 4
    assert text[start:text.index("<!-- end of generated section -->")] == schema.reference()
