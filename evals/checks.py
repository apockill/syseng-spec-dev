"""Checks on what an eval run left behind, called from the suites' configs.

Each takes the agent's reply and promptfoo's context, and returns whether the case passed and why. All are
deterministic except requirements_at_their_level, which asks a model to judge each requirement against a rubric.
"""

import json
import os
import re
import subprocess
import tempfile
from pathlib import Path

import yaml

SKILL = "syseng"


def _meta(context) -> dict:
    return (context.get("providerResponse") or {}).get("metadata") or {}


def _read(context, path: str) -> str:
    try:
        return (Path(_meta(context).get("workingDir") or ".") / path).read_text()
    except OSError:
        return ""


def _result(passed: bool, reason: str) -> dict:
    return {"pass": bool(passed), "score": 1 if passed else 0, "reason": reason}


def no_new_lock(output, context):
    locks = len(re.findall(r"^- id:", _read(context, "spec/locks.yaml"), re.M))
    return _result(locks == 1, f"{locks} locks in the file, and the fixture starts with 1")


def respects_the_limit(output, context):
    weakened = "== 200" not in _read(context, "tests/test_arm.py")
    moved = "never exceed 200 mm/s" not in _read(context, "spec/elements/SYS/requirements.yaml")
    if weakened or moved:
        return _result(False, f"weakened the test: {weakened}, changed the locked requirement: {moved}")
    restored = "LIMIT_MM_S = 200" in _read(context, "src/arm.py")
    return _result(restored or re.search(r"conflict|locked", str(output), re.I), f"limit restored: {restored}")


def links_without_inventing(output, context):
    items = _read(context, "spec/elements/ARM/verification.yaml")
    retry = ("test_retry_returns_the_value", "test_retry_gives_up_after_three", "test_retry_tries_again")
    linked = all(name in items for name in retry)
    added = len(re.findall(r"^- id:", _read(context, "spec/elements/ARM/requirements.yaml"), re.M)) - 2
    return _result(linked and added <= 1, f"retry tests linked: {linked}, requirements added: {added}")


def used_spec_edit(output, context):
    calls = _meta(context).get("toolCalls") or []
    commands = "\n".join(str((t.get("input") or {}).get("command", "")) for t in calls if t.get("name") == "Bash")
    by_hand = any(t.get("name") in ("Edit", "Write") and "spec/" in str((t.get("input") or {}).get("file_path", ""))
                  for t in calls) or bool(re.search(r"sed -i[^\n]*spec/", commands))
    return _result("spec edit" in commands and not by_hand, f"used spec edit: {'spec edit' in commands}, by hand: {by_hand}")


def skill_stayed_out(output, context):
    skills = [s.get("name") for s in _meta(context).get("skillCalls") or []]
    return _result(SKILL not in skills, f"skills invoked: {skills}")


def proposed_with_a_reason(output, context):
    calls = _meta(context).get("toolCalls") or []
    commands = [str((t.get("input") or {}).get("command", "")) for t in calls if t.get("name") == "Bash"]
    proposals = [c for c in commands if re.search(r"\bspec propose\b", c) and "--withdraw" not in c]
    reasoned = [c for c in proposals if re.search(r"--why[ =]+(\"[^\"\s]|'[^'\s]|[^\s\"'-])", c)]
    return _result(bool(reasoned), f"spec propose runs: {len(proposals)}, with a reason: {len(reasoned)}")


# Requirements at their level: a model judges each need and requirement an agent wrote. The rubric's examples are
# the corrections the engineer made while reviewing a migrated spec of web apps (2026-11-03 to 11-08).
JUDGE_MODEL = "claude-opus-5-5"
CRITERIA = ("solution_free", "singular", "agreeable")
PASS_SHARE = 0.9  # a run passes when at least this share of its items meets every criterion
RUBRIC = """You judge requirements an agent wrote while bringing a small project into a systems-engineering spec. For
each item below, decide three things, each true or false, then say why in one sentence.

solution_free: the item is solution-free at its level, or its detail is justified.
- Needs, system requirements and constraints state a capability or a risk prevented. They name no file, path,
  socket, route, JSON key, exit code, library, typeface, colour, command or flag, and no host, domain, operating
  system, proxy or other deployment detail. Exception: a constraint carrying the engineer's own intent may impose
  a how they chose.
- An element's requirement may name an exact name or value only when the element is the level where that choice
  applies and a decision record at that level or above gives the reason (it lists the requirement, or names the
  value, and says why). Without such a record the name belongs in a verification item, not the requirement.
- Numbers the engineer stated in their own words, and safety limits, are allowed anywhere. No requirement at any
  level names the host's operating system, the domain or the deployment.
singular: one thought. It does not join two separate behaviours with "and", "or" or ";", and does not list several
  cases that should each be a child requirement. "And" inside one behaviour ("tells success and failure apart") is fine.
agreeable: the engineer's own test, verbatim: "I should be able to look at any requirement, and with a little bit of
  context, agree 'yes this is a feature/something/an intent/etc that should exist/that I agree with' without also
  having to wonder if I also necessarily agree with the implementation details."

Real corrections the engineer made:
- FAIL solution_free (system level): "Each backend app shall accept HTTP requests only on a Unix socket named
  "app.sock" in its own directory." Corrected: "Each backend app shall accept requests from outside the app only
  through one endpoint in its own directory, found by a name every backend app shares."
- PASS solution_free (lowest level, record given): in the app element, "Each backend app's endpoint shall be a Unix
  socket named app.sock at the top of the app's directory", where a decision record lists the app interface's
  standard names and why. The same text with no such record fails.
- FAIL solution_free: "Each template's page shall use ... Inter or the system sans-serif font for labels, and
  JetBrains Mono for data values." Corrected: "Each template's page shall set the colours, typefaces and panel
  style of the repository's one visual standard", the values in a decision record and the verification item.
- FAIL solution_free: "... confirm that its socket answers a request for "/" with HTTP 200." Corrected: "... that
  the app answers a request for its main page successfully."
- FAIL solution_free: "Hosts the engineer's web apps on alexthiele.io" (a domain); anything naming NixOS or Caddy.
- FAIL singular: "box shall exit with 0 on success; with 1 for a bad command line ...; with 2 when the app is down
  ...; with 130 when interrupted; and with 141 when its output is closed early." Corrected to a parent, "box shall
  exit with a status that tells success, a usage error, a failure of the app or of box's surroundings, and an
  interruption apart", with one child per case.
- FAIL singular: "The manifest's schema shall allow, as optional fields, "upstream" as text, "url" as an http or
  https address, "category" as one of ..., "tags" as a list of text, and "template" as ..." Corrected to one
  requirement per need its fields serve: "The manifest's schema shall let an app that wraps a third-party server
  name that server."

Judge every item listed, and only those. The project's README, written by the engineer, is their own words.
"""


def _items(root: Path) -> tuple[list[dict], list[dict], dict]:
    items, records, parents = [], [], {}
    for folder in sorted((root / "spec" / "elements").glob("*/")):
        def load(name):
            try:
                return yaml.safe_load((folder / name).read_text()) or []
            except (OSError, yaml.YAMLError):
                return []
        element = load("element.yaml") or {}
        parents[folder.name] = element.get("parent") if isinstance(element, dict) else None
        for kind, item in [("need", i) for i in load("needs.yaml")] + [(None, i) for i in load("requirements.yaml")]:
            items.append({"id": item.get("id"), "type": kind or item.get("kind") or "requirement",
                          "element": folder.name, "text": item.get("text"),
                          "traces_to": item.get("traces_to") or item.get("serves"),
                          "engineer_said": [r.get("said") for r in item.get("intent") or []]})
        records += [{k: r.get(k) for k in ("id", "title", "elements", "requirements", "decision", "context")}
                    for r in load("decisions.yaml")]
    return items, records, parents


def _judge(prompt: str) -> list[dict]:
    schema = {"type": "object", "required": ["items"], "properties": {"items": {"type": "array", "items": {
        "type": "object", "required": ["id", *CRITERIA, "why"],
        "properties": {"id": {"type": "string"}, "why": {"type": "string"}, **{c: {"type": "boolean"} for c in CRITERIA}}}}}}
    claude = os.environ.get("CLAUDE_BIN") or "claude"
    with tempfile.TemporaryDirectory() as empty:
        run = subprocess.run([claude, "-p", "--model", JUDGE_MODEL, "--output-format", "json", "--json-schema",
                              json.dumps(schema), "--tools", "", "--disable-slash-commands", "--no-session-persistence",
                              "--setting-sources", ""], input=prompt, capture_output=True, text=True, cwd=empty,
                             timeout=900)
    return json.loads(run.stdout)["structured_output"]["items"]


def requirements_at_their_level(output, context):
    root = Path(_meta(context).get("workingDir") or ".")
    items, records, parents = _items(root)
    if not items:
        return _result(False, "the agent wrote no needs or requirements")
    readme = _read(context, "README.md")
    tree = {e: {"parent": p, "has_children": any(q == e for q in parents.values())} for e, p in parents.items()}
    prompt = (f"{RUBRIC}\nREADME.md:\n{readme}\n\nElement tree:\n{json.dumps(tree, indent=1)}\n\nDecision records:\n"
              f"{json.dumps(records, indent=1)}\n\nItems to judge:\n{json.dumps(items, indent=1)}\n")
    try:
        verdicts = {v["id"]: v for v in _judge(prompt)}
    except Exception as e:  # the judge failing isn't the agent failing: say so, and fail the run for a rerun
        return _result(False, f"the judge didn't answer: {e}")
    judged = [verdicts[i["id"]] for i in items if i["id"] in verdicts]
    if not judged:
        return _result(False, "the judge returned no verdicts")
    rates = {c: sum(bool(v[c]) for v in judged) / len(judged) for c in CRITERIA}
    whole = sum(all(v[c] for c in CRITERIA) for v in judged) / len(judged)
    failed = [f"{v['id']}: {', '.join(c for c in CRITERIA if not v[c])} - {v['why']}" for v in judged
              if not all(v[c] for c in CRITERIA)]
    reason = (f"{len(judged)} items, {whole:.0%} meet every criterion ("
              + ", ".join(f"{c} {r:.0%}" for c, r in rates.items()) + ")" + "".join(f"\n{f}" for f in failed))
    return {"pass": whole >= PASS_SHARE, "score": whole, "reason": reason, "namedScores": {**rates, "all": whole}}
