"""Wording rules (MODEL-16, MODEL-17), including the calibrated exemptions (DR-30)."""

import pytest

from syseng.rules import check_wording


def codes(text: str) -> list[str]:
    return [i.code for i in check_wording(text)]


@pytest.mark.parametrize("text", [
    "The toolkit shall run the checker.",
    "When the agent tries to finish, the toolkit shall run the checker.",
    "In spec-first mode, when a contradiction matters, the agent shall stop and ask.",
    "At the end of a full run, the toolkit shall produce a summary.",
    "The toolkit's skills, subagent definitions, code and documentation shall contain no host names.",
    'Requirement text shall contain exactly one "shall".',
    "The spec shall allow no limit on how many system elements a file relates to.",
    "Requirement text shall follow the EARS (Easy Approach to Requirements Syntax) patterns.",
    "The toolkit shall support both reviewing before and reviewing after.",
])
def test_good_requirements_pass(text):
    assert codes(text) == []


@pytest.mark.parametrize("text, code", [
    ("The toolkit runs the checker.", "W001"),
    ("The toolkit shall run the checker and shall report findings.", "W001"),
    ("Shall run the checker.", "W002"),
    ("The toolkit shall run the checker where possible.", "W003"),
    ("The toolkit shall report errors, warnings, etc.", "W004"),
    ("The toolkit shall run tests and/or checks.", "W004"),
    ("The toolkit shall make review easier.", "W005"),
    ("The toolkit shall respond quickly.", "W005"),
    ("The engineer shall be able to approve items.", "W006"),
    ("The toolkit shall accept any finding.", "W007"),
    ("The toolkit shall sort findings in order to save time.", "W008"),
    ("The toolkit shall call `run_checks()` first.", "W009"),
    ("The toolkit shall read the config.yaml file.", "W009"),
    ("The toolkit shall call loadSpec on start.", "W009"),
    ("The checker shall be verified by a unit test.", "W010"),
])
def test_each_rule_fires(text, code):
    assert code in codes(text)


def test_quoted_shall_is_a_mention_not_an_obligation():
    assert "W001" not in codes('The rules shall require one "shall" per sentence.')


def test_capitalized_vague_word_at_sentence_start_still_counts():
    assert "W005" in codes("Many findings shall appear first.")


def test_issue_spans_point_at_the_offending_words():
    text = "The toolkit shall run the checker where possible."
    issue = next(i for i in check_wording(text) if i.code == "W003")
    assert text[issue.span[0]:issue.span[1]] == "where possible"
