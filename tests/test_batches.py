"""YAML that agents send, read as they meant it (CLI-36, CLI-37, DR-80).

YAML ends an unquoted value at ` #` and reads `: ` inside one as a new key. In the onboarding of a web-apps folder
on 2026-11-03, 3 of 5 agents lost text to the first with no warning, and 2 of 5 met the second as a bare parse error.
"""

import re

import pytest
import yaml

from syseng import cli, changes, edit, feedback, init, yamlio


def test_a_comment_after_a_prose_value_is_refused_naming_the_line_and_key():
    batch = "edits:\n  - add: requirement\n    element: CORE\n    text: The page uses the #090d16 background\n"
    with pytest.raises(yamlio.BatchError) as e:
        yamlio.loads_batch(batch)
    msg = str(e.value)
    assert "line 4" in msg and "`text`" in msg and "'The page uses the'" in msg and "quotes" in msg


def test_a_comment_that_reads_as_one_is_refused_after_any_prose_field():
    for key in ("title", "why", "said", "reason", "question", "detail"):
        with pytest.raises(yamlio.BatchError, match=f"`{key}`"):
            yamlio.loads_batch(f"{key}: Short words   # a note the agent meant as a comment\n")


def test_a_hash_glued_to_a_word_is_refused_after_any_value():
    with pytest.raises(yamlio.BatchError, match="`element`"):
        yamlio.loads_batch("element: CORE #12\n")


def test_comments_on_their_own_lines_and_after_short_values_still_work():
    doc = yamlio.loads_batch(
        "# a batch\nedits:\n  - add: system          # or: constraint\n"
        "    # the text follows\n    text: \"Uses the #090d16 background\"\n"
        "    by: Ada <ada@example.com>   # filled in when left out\n    basis: derived  #\n"
        "    involves: [CORE-1]           # the nodes it's about\n    why: |\n      Hex #090d16 in a block.\n")
    e = doc["edits"][0]
    assert e["add"] == "system" and e["text"] == "Uses the #090d16 background" and e["by"] == "Ada <ada@example.com>"
    assert e["why"].startswith("Hex #090d16") and e["involves"] == ["CORE-1"]


def test_an_acknowledgment_note_is_prose():
    with pytest.raises(yamlio.BatchError, match="`CORE-V1`"):
        yamlio.loads_batch("acks:\n  CORE-V1: still checks the color #090d16\n")


def test_a_colon_inside_a_value_names_the_key_and_says_to_quote_it():
    with pytest.raises(yamlio.BatchError) as e:
        yamlio.loads_batch("edits:\n  - modify: CORE-1\n    reason: The rule: always quote\n")
    msg = str(e.value)
    assert "line 3" in msg and "`reason`" in msg and "quotes" in msg and "The rule: always quote" in msg


def test_other_yaml_errors_show_the_line():
    with pytest.raises(yamlio.BatchError, match="line 2"):
        yamlio.loads_batch("a: [1, 2\nb: 3\n")


def test_edit_and_decide_refuse_such_a_batch_and_write_nothing(spec, capsys, tmp_path):
    spec.write()
    changes.start(spec.load(), "Colors", None, None, None)
    path = tmp_path / "b.yaml"
    path.write_text("edits:\n  - modify: CORE-1\n    set:\n      text: The core shall stamp #1 widgets.\n"
                    "    reason: r\n")
    assert cli.main(["--spec", str(spec.root), "edit", "--file", str(path)]) == 1
    out = capsys.readouterr().out
    assert "line 4" in out and "`text`" in out
    assert spec.load().items["CORE-1"].data["text"] == "The core shall stamp each widget."
    path.write_text("question: Paint it #090d16?\nimportance: i\noptions:\n  - label: a\n    recommended: true\n"
                    "  - label: b\n")
    assert cli.main(["--spec", str(spec.root), "decide", "--file", str(path)]) == 1
    assert "`question`" in capsys.readouterr().out
    assert not changes.current(spec.load()).data.get("decisions")


def test_a_hand_written_feedback_block_is_read_the_same_way():
    with pytest.raises(feedback.FeedbackError, match="`general`"):
        feedback.parse("review: r\nby: Ada <ada@example.com>\ngeneral: Use #090d16 here # please\n")


def _yaml_blocks(text: str):
    for block in re.findall(r"```[a-z]*\n(.*?)```", text, re.S):
        lines = [ln for ln in block.splitlines() if not re.match(r"^\s*(spec |YAML\s*$)", ln)]
        body = "\n".join(lines) + "\n"
        try:
            yaml.safe_load(body)
        except yaml.YAMLError:
            continue  # not YAML: a command line, a tree or prose
        yield body


@pytest.mark.parametrize("path", sorted(init.SKILL.rglob("*.md")), ids=lambda p: p.name)
def test_the_skills_own_examples_pass(path):
    for body in _yaml_blocks(path.read_text()):
        yamlio.loads_batch(body)


def test_the_edit_commands_own_example_passes():
    example = edit.__doc__.split("An edit is a batch of operations, sent as one YAML document:")[1]
    example = example.split("What a person asked for")[0]
    doc = yamlio.loads_batch("\n".join(ln[4:] for ln in example.splitlines()))
    assert doc["edits"][0]["text"] == "The CLI shall …"
