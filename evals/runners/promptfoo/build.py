"""Writes a promptfoo config from evals.json. The only file that knows promptfoo's config format.

Each case runs twice, with and without the skill. An assertion becomes a judged rubric, and a check calls checks.py.
Usage: build.py <evals.json> <working folder>
"""

import json
import os
import shutil
import sys
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
# Read-only commands agents reach for, so their ordinary habits aren't blocked; writes stay limited to the workspace.
TOOLS = ["Read", "Grep", "Glob", "Edit", "Write", "Bash", "Skill"]
COMMANDS = ["spec", "git status", "git diff", "git log", "git show", "python3 -m pytest", "python -m pytest", "cat", "head",
            "tail", "ls", "grep", "rg", "wc", "sed -n", "find . ", "which", "echo"]


def _provider(label: str, workspace: Path, claude: str, skill: bool) -> dict:
    config = {"model": "claude-sonnet-5-5", "apiKeyRequired": False, "path_to_claude_code_executable": claude,
              "working_dir": str(workspace), "copy_working_dir": "copy", "permission_mode": "acceptEdits",
              "max_turns": 25, "tools": TOOLS, "setting_sources": ["project"] if skill else [],
              "skills": ["syseng"] if skill else [],
              "append_allowed_tools": ["Read", "Grep", "Glob", "Edit", "Write", *[f"Bash({c}*)" for c in COMMANDS]]}
    return {"id": "anthropic:claude-agent-sdk", "label": label, "config": config}


def _test(case: dict) -> dict:
    asserts = [{"type": "llm-rubric", "value": text} for text in case.get("assertions") or []]
    asserts += [{"type": "python", "value": f"file://{HERE / 'check.py'}:{name}"} for name in case.get("checks") or []]
    return {"description": case["id"], "vars": {"request": case["prompt"]}, "assert": asserts}


def build(suite: dict, work: Path, claude: str) -> dict:
    judge = {"id": "anthropic:claude-agent-sdk",
             "config": {"model": "claude-haiku-5-5", "apiKeyRequired": False, "path_to_claude_code_executable": claude}}
    return {"description": f"{suite['skill_name']} skill evals", "prompts": ["{{request}}"],
            "providers": [_provider("with-skill", work / "fixture" / "with-skill", claude, True),
                          _provider("without-skill", work / "fixture" / "base", claude, False)],
            "defaultTest": {"options": {"provider": judge}},
            "tests": [_test(case) for case in suite["evals"]]}


if __name__ == "__main__":
    path, work = Path(sys.argv[1]), Path(sys.argv[2]).resolve()
    claude = os.path.realpath(shutil.which("claude") or "claude")  # the SDK's bundled binary doesn't run on every system
    print(yaml.safe_dump(build(json.loads(path.read_text()), work, claude), sort_keys=False))
