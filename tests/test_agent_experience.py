"""What agents see: commands they can type, and no toolkit-internal IDs in a host repository (CLI-15, AGENT-58)."""

import io
import re

from syseng import changes, cli, edit, init, model

TOOLKIT_ID = re.compile(r"\b(?:SYS|AGENT|CHECK|MODEL|CLI|CHANGE|REVIEW|REASON|VERIFY|LANG|ONBOARD|UNIT|INTEG|NEED|DR)"
                        r"-V?\d+\b")
EXAMPLES = {"CHECK-3", "CHECK-5", "CHECK-9", "CLI-3", "CLI-9", "CLI-V1", "DR-41", "SYS-7", "NEED-1",
            "NEED-12"}  # illustrations of the format, not citations


def _set_up(spec, tmp_path, monkeypatch):
    root = spec.write()
    init.run(root.parent, ["claude-code"])
    return root


def _run(*argv, capsys) -> str:
    cli.main(list(argv))
    return capsys.readouterr().out


def test_messages_name_the_spec_command(spec, tmp_path, monkeypatch, capsys):
    root = _set_up(spec, tmp_path, monkeypatch)
    assert "`spec check --todo`" in _run("--spec", str(root), "check", capsys=capsys)
    assert "`spec render`" in (root / "requirements.md").read_text()


def test_a_host_repository_sees_no_toolkit_requirement_ids(spec, tmp_path, monkeypatch, capsys):
    root = _set_up(spec, tmp_path, monkeypatch)
    host_ids = set(model.load(root).items)
    seen = _run("--spec", str(root), "check", "--todo", capsys=capsys)
    seen += _run("--spec", str(root), "show", "CORE-1", capsys=capsys)
    changes.start(model.load(root), "widgets", None, None, None)
    result = edit.run(root, {"edits": [{"modify": "CORE-1", "set": {"text": "The core shall stamp it."},
                                        "reason": "shorter"}]})
    seen += "\n".join(result.context)
    for path in [*root.rglob("*.md"), root.parent / "AGENTS.md", *init.SKILL.rglob("*.md"),
                 *init.AGENT_DEFINITIONS.glob("*.md")]:
        seen += path.read_text()
    for sub in ("edit", "init", "approve", "propose", "status"):
        try:
            cli.main([sub, "--help"])
        except SystemExit:
            pass
        seen += capsys.readouterr().out
    leaked = set(TOOLKIT_ID.findall(seen)) - host_ids - EXAMPLES
    assert leaked == set(), leaked


def _worded_core_change(spec):
    spec.files["elements/CORE/requirements.yaml"][0].update({"origin": "engineer", "source": '"stamp them"'})
    root = spec.write()
    changes.start(spec.load(), "restamp", None, None, None)
    return root


def test_a_batch_can_be_retried_with_acknowledgments_alone(spec, capsys, monkeypatch, tmp_path):
    (tmp_path / "tmp").mkdir()
    monkeypatch.setattr(edit.tempfile, "gettempdir", lambda: str(tmp_path / "tmp"))
    root = _worded_core_change(spec)
    monkeypatch.setattr("sys.stdin", io.StringIO(
        "edits:\n  - modify: CORE-1\n    set: {text: The core shall stamp each widget twice.}\n    reason: twice\n"))
    assert cli.main(["--spec", str(root), "edit"]) == 2
    out = capsys.readouterr().out
    assert "`spec edit --retry --ack 'CORE-1=<note>' --ack 'CORE-V1=<note>'`" in out
    assert cli.main(["--spec", str(root), "edit", "--retry", "--ack", "CORE-1=twice is the rule now",
                     "--ack", "CORE-V1=still checks a stamp"]) == 0
    assert "twice" in model.load(root).items["CORE-1"].data["text"]
    assert cli.main(["--spec", str(root), "edit", "--retry"]) == 1      # nothing left to retry
    assert "there's no batch to retry" in capsys.readouterr().out


def test_status_says_what_is_open_and_what_awaits_the_engineer(spec, capsys):
    root = _worded_core_change(spec)
    acks = {"CORE-1": "fine", "CORE-V1": "fine"}
    edit.run(root, {"edits": [{"modify": "CORE-1", "set": {"text": "The core shall stamp it twice."},
                               "reason": "twice"}], "acks": acks})
    out = _run("--spec", str(root), "status", capsys=capsys)
    assert "Open change:" in out and "asked: restamp" in out
    assert "Keep it: `CORE-1 LGTM`" in out and "spec check:" in out


def test_edit_context_keeps_the_lines_of_multi_line_text(spec):
    root = spec.write()
    changes.start(spec.load(), "widgets", None, None, None)
    result = edit.run(root, {"edits": [{"modify": "CORE-1", "set": {"why": "first line\nsecond line"},
                                        "reason": "two lines"}]}, dry_run=True)
    assert "      first line" in result.context and "      second line" in result.context


def test_the_engineers_words_are_never_rewritten(spec, tmp_path, monkeypatch):
    spec.files["elements/CORE/requirements.yaml"][0]["quotes"] = [
        {"words": "just run `spec edit` for it", "said": "2026-10-17 09:00", "context": "talking about edits"}]
    root = _set_up(spec, tmp_path, monkeypatch)
    text = (root / "requirements.md").read_text()
    assert "just run `spec edit` for it" in text


def test_f_strings_keep_to_what_python_3_11_accepts():
    """Before 3.12, an f-string's expressions can't hold a backslash or the quote that closes the f-string."""
    import ast
    from pathlib import Path
    for path in (Path(__file__).resolve().parents[1] / "src" / "syseng").rglob("*.py"):
        src = path.read_text()
        for node in ast.walk(ast.parse(src)):
            if not isinstance(node, ast.JoinedStr):
                continue
            whole = (ast.get_source_segment(src, node) or "").lstrip("rRbBfF")
            closing = whole[:3] if whole[:3] in ('"""', "\'\'\'") else whole[:1]
            for v in node.values:
                if isinstance(v, ast.FormattedValue):
                    expr = ast.get_source_segment(src, v.value) or ""
                    assert "\\" not in expr and closing not in expr, f"{path.name}:{v.lineno}: {expr}"
