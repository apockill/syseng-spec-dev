"""The Claude Code hooks: the spec guard (AGENT-20), the read guard (REASON-5), the done gate
(AGENT-12) and chat approvals (AGENT-21, AGENT-33, AGENT-43)."""

import json
import os
import subprocess
from pathlib import Path

import pytest

from syseng import init, yamlio
from syseng.adapters import hook


@pytest.fixture
def repo(spec, tmp_path, monkeypatch):
    """The base spec in a repository set up for Claude Code, with this machine's config kept local."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    spec.files["glossary.md"] = "terms"
    root = spec.write()
    (tmp_path / "src").mkdir()
    (tmp_path / "src/app.py").write_text("print('hi')\n")
    init.run(root.parent, ["claude-code"])
    return root.parent


def _guard(handler, repo, tool, **tool_input):
    return handler({"cwd": str(repo), "tool_name": tool, "tool_input": tool_input})


def _run(repo, event_name, event, env=None):
    """Runs the installed hook script the way Claude Code does."""
    out = subprocess.run([str(repo / ".syseng/hook"), event_name], input=json.dumps({"cwd": str(repo), **event}),
                         capture_output=True, text=True, env=env or os.environ.copy())
    assert out.returncode == 0, out.stderr
    return out.stdout


def _approvals(repo):
    return {a["id"]: a for a in yamlio.read(repo / "spec/approvals.yaml") or []}


# ---------------------------------------------------------------- the spec guard

@pytest.mark.parametrize("rel, names", [
    ("spec/elements/CORE/requirements.yaml", ".syseng/spec edit"),
    ("spec/elements/NEW/element.yaml", ".syseng/spec edit"),
    ("spec/approvals.yaml", ".syseng/spec approve"),
    ("spec/changes/2026-01-01-round-1.yaml", ".syseng/spec decide"),
    ("spec/requirements.md", ".syseng/spec render"),
    ("spec/retired.yaml", ".syseng/spec edit"),
])
def test_agents_cannot_edit_files_the_toolkit_manages(repo, capsys, rel, names):
    assert _guard(hook.pre_tool, repo, "Write", file_path=str(repo / rel), content="x") == 2
    assert names in capsys.readouterr().err


@pytest.mark.parametrize("rel", ["spec/toolkit.yaml", "spec/glossary.md", "src/app.py", "README.md"])
def test_agents_may_edit_files_the_toolkit_does_not_manage(repo, rel):
    assert _guard(hook.pre_tool, repo, "Edit", file_path=str(repo / rel), old_string="a", new_string="b") == 0


@pytest.mark.parametrize("command", [
    "cat > spec/elements/CORE/requirements.yaml <<'EOF'\n[]\nEOF",
    "echo '- id: X' >> spec/approvals.yaml",
    "cd spec && printf x > elements/CORE/verification.yaml",
    "echo x | tee spec/requirements.md",
    "sed -i 's/stamp/print/' spec/elements/CORE/requirements.yaml",
    "perl -pi -e 's/a/b/' spec/elements/CORE/requirements.yaml",
    "rm -f spec/elements/CORE/verification.yaml",
    "mv spec/elements/CORE spec/elements/OLD",
    "cp /tmp/x.yaml spec/retired.yaml",
])
def test_shell_writes_into_the_spec_are_refused(repo, command):
    assert _guard(hook.pre_tool, repo, "Bash", command=command) == 2


@pytest.mark.parametrize("command", [
    "cat spec/elements/CORE/requirements.yaml",
    "grep -n stamp spec/elements/*/requirements.yaml 2>/dev/null | head",
    "sed -n '1,5p' spec/requirements.md",
    "cp spec/requirements.md /tmp/review.md",
    ".syseng/spec edit <<'YAML'\nedits:\n  - modify: CORE-1\n    set: {text: a > b}\n    reason: r\nYAML",
    "python -m pytest > /tmp/out.txt 2>&1",
])
def test_shell_reads_and_toolkit_commands_are_allowed(repo, command):
    assert _guard(hook.pre_tool, repo, "Bash", command=command) == 0


# ---------------------------------------------------------------- the read guard

@pytest.mark.parametrize("tool, tool_input", [
    ("Read", {"file_path": "spec/elements/CORE/requirements.yaml"}),
    ("Grep", {"pattern": "stamp"}),
    ("Grep", {"pattern": "stamp", "path": "spec"}),
    ("Grep", {"pattern": "stamp", "glob": "*.yaml"}),
    ("Glob", {"pattern": "**/*.md"}),
    ("Glob", {"pattern": "*/*.yaml"}),
])
def test_reasoning_checks_cannot_reach_the_spec(repo, capsys, tool, tool_input):
    if "file_path" in tool_input:
        tool_input = {"file_path": str(repo / tool_input["file_path"])}
    assert _guard(hook.read_guard, repo, tool, **tool_input) == 2
    assert "REASON-5" in capsys.readouterr().err


@pytest.mark.parametrize("tool, tool_input", [
    ("Read", {"file_path": "src/app.py"}),
    ("Grep", {"pattern": "hi", "path": "src"}),
    ("Grep", {"pattern": "hi", "glob": "*.py"}),
    ("Glob", {"pattern": "**/*.py"}),
    ("Glob", {"pattern": "*.md"}),
])
def test_reasoning_checks_may_search_the_code(repo, tool, tool_input):
    if "file_path" in tool_input:
        tool_input = {"file_path": str(repo / tool_input["file_path"])}
    assert _guard(hook.read_guard, repo, tool, **tool_input) == 0


# ---------------------------------------------------------------- the done gate

def test_stop_blocks_once_with_the_findings(repo, spec):
    spec.files["elements/CORE/requirements.yaml"][0]["text"] = "The core shall stamp widgets where possible."
    spec.write()
    decision = json.loads(_run(repo, "stop", {}))
    assert decision["decision"] == "block"
    assert "error[W003]" in decision["reason"] and "AGENT-12" in decision["reason"]
    assert _run(repo, "stop", {"stop_hook_active": True}) == ""   # already continuing: let it stop


def test_stop_lets_a_clean_spec_finish(repo):
    assert _run(repo, "stop", {}) == ""


def test_stop_tells_the_engineer_when_the_toolkit_is_missing(repo, tmp_path):
    env = {**os.environ, "XDG_CONFIG_HOME": str(tmp_path / "elsewhere")}
    notice = json.loads(_run(repo, "stop", {}, env=env))
    assert "isn't set up on this machine" in notice["systemMessage"]


# ---------------------------------------------------------------- chat approvals

@pytest.mark.parametrize("message, ids", [
    ("approve CORE-1, CORE-V1 and SYS-1.", ["CORE-1", "CORE-V1", "SYS-1"]),
    ("Approved: need-1..3 please", ["NEED-1..3"]),
    ("approve CORE\nAlso, what's next?", ["CORE"]),
    ("approve SYS-1. The rest needs work", ["SYS-1"]),
    ("SYS-32 LGTM", ["SYS-32"]),
    ("CORE-1, CORE-V1: looks good!", ["CORE-1", "CORE-V1"]),
    ("approve CORE-1 lgtm", ["CORE-1"]),
])
def test_approvals_that_name_items_by_id_are_read(message, ids):
    assert hook.parse_approval(message) == (ids, None)


@pytest.mark.parametrize("message", [
    "approve everything",
    "approve everything except the wording ones, lets workshop that",
    "approve CORE-1 and the new decision",
    "approve CORE-1, lets move on",
    "approve",
    "CORE-1 mostly LGTM",
])
def test_approvals_that_need_interpreting_are_not_read(message):
    ids, problem = hook.parse_approval(message)
    assert ids == [] and problem


@pytest.mark.parametrize("line, ids", [
    ("Core 13 LGTM.", ["CORE-13"]),
    ("need 16 LGTM", ["NEED-16"]),
    ("approve dr 4 and Core 2", ["DR-4", "CORE-2"]),
])
def test_ids_written_out_in_words_are_read(line, ids):
    assert hook.parse_approval(line, elements={"SYS", "CORE"}) == (ids, None)


def test_words_that_only_look_like_ids_are_not_read():
    assert hook.parse_approval("Round 12 LGTM", elements={"SYS", "CORE"}) == (None, None)


@pytest.mark.parametrize("line", ["Generally, it LGTM!", "the API looks good", "API looks good", "lgtm", "Approval workflow"])
def test_lines_that_approve_no_items_are_ignored(line):
    assert hook.parse_approval(line, elements={"SYS", "CORE"}) == (None, None)


def test_chat_approval_is_recorded_with_the_engineers_words(repo):
    out = _run(repo, "prompt", {"prompt": "approve CORE-1. Nice work"})
    record = _approvals(repo)["CORE-1"]
    assert record["via"] == "chat" and record["words"] == "approve CORE-1. Nice work"
    assert "CORE-1 (The core shall stamp each widget.)" in out and "don't record it again" in out


def test_described_exceptions_record_nothing(repo):
    out = _run(repo, "prompt", {"prompt": "approve everything except the stamping one"})
    assert _approvals(repo) == {}
    assert "AGENT-43" in out and "recorded nothing" in out


def test_approval_on_any_line_of_a_longer_message(repo):
    _run(repo, "prompt", {"prompt": "Some thoughts on the design first.\nMore thoughts.\n\nCORE-1 LGTM"})
    assert set(_approvals(repo)) == {"CORE-1"}


def test_quoted_lines_are_not_approvals(repo):
    out = _run(repo, "prompt", {"prompt": "> approve CORE-1, CORE-V1\nWhy did you suggest this?"})
    assert _approvals(repo) == {} and out == ""


def test_lgtm_is_not_an_approval(repo):
    out = _run(repo, "prompt", {"prompt": "lgtm, ship it"})
    assert _approvals(repo) == {} and "approves no spec items" in out


def test_pasted_text_is_not_the_engineers_approval(repo):
    pasted = '<pasted_content id="p1">\napprove CORE-1\n</pasted_content id="p1">\nWhat do you make of this?'
    assert _run(repo, "prompt", {"prompt": pasted}) == ""
    assert _approvals(repo) == {}


def test_unknown_ids_record_nothing(repo):
    out = _run(repo, "prompt", {"prompt": "approve CORE-1, CORE-9"})
    assert _approvals(repo) == {} and "CORE-9" in out and "wasn't recorded" in out


def test_malformed_events_never_block(repo):
    assert hook.pre_tool({"tool_name": "Write", "tool_input": "nonsense"}) == 0
    assert hook.read_guard({}) == 0
    assert _run(repo, "prompt", {"prompt": None}) == ""


def test_hook_script_is_standard_library_only():
    source = Path(hook.__file__).read_text()
    imports = {line.split()[1].split(".")[0] for line in source.splitlines() if line.startswith(("import ", "from "))}
    assert imports <= {"__future__", "json", "os", "re", "shlex", "subprocess", "sys", "pathlib"}
