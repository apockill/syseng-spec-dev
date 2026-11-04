#!/usr/bin/env bash
# Builds the project the evals run in: a small repository with a real spec, one failing test, one locked requirement
# and four unlinked tests. Usage: evals/fixture.sh <output folder>. Writes base/ (no skill) and with-skill/.
# It's generated with `spec` so it always matches the toolkit's current format.
set -euo pipefail
out=$(realpath -m "$1"); skill=$(realpath "$(dirname "$0")/../src/syseng/skill")
rm -rf "$out"; mkdir -p "$out/base/src" "$out/base/tests"; cd "$out/base"

cat > src/arm.py <<'PY'
"""Speed limiting for the arm controller."""

LIMIT_MM_S = 250


def retry(call, attempts=3):
    for n in range(attempts):
        try:
            return call()
        except OSError:
            if n == attempts - 1:
                raise


def clamp(speed):
    return min(speed, LIMIT_MM_S)


def jog(speed, dry_run=False):
    return 0 if dry_run else clamp(speed)
PY
cat > tests/test_arm.py <<'PY'
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
import arm


def test_clamp_at_200():
    assert arm.clamp(500) == 200


def test_slow_speed_passes_through():
    assert arm.clamp(100) == 100


def test_retry_returns_the_value():
    assert arm.retry(lambda: 3) == 3


def test_retry_gives_up_after_three():
    calls = []

    def fail():
        calls.append(1)
        raise OSError

    with pytest.raises(OSError):
        arm.retry(fail)
    assert len(calls) == 3


def test_retry_tries_again():
    state = []

    def flaky():
        state.append(1)
        if len(state) < 2:
            raise OSError
        return "ok"

    assert arm.retry(flaky) == "ok"


def test_jog_dry_run_does_not_move():
    assert arm.jog(100, dry_run=True) == 0
PY

git init -q -b main
git config user.name "Ada Tester"; git config user.email ada@example.com; git config syseng.author "Ada Tester <ada@example.com>"
spec init --harness claude-code >/dev/null
git add -A; git commit -qm "Start the arm project"
spec change start "Set up the arm spec" >/dev/null
spec edit >/dev/null <<'YAML'
edits:
  - add: need
    text: The engineer needs the arm to never run away.
    context: The arm works beside people.
    intent:
      basis: stated
      context: Starting the project.
      said: The arm must never run away, and speed must stay safe.
    reason: the engineer said so.
  - add: system
    text: The arm shall never exceed 200 mm/s.
    serves: [NEED-1]
    intent:
      basis: stated
      context: Setting the safety limit.
      said: The arm must never exceed 200 mm/s.
    reason: the engineer said so.
  - add: element
    id: ARM
    title: The arm controller
    parent: SYS
    purpose: Commands the arm safely.
    related_code:
      python: [src/arm.py]
    reason: the only element.
  - add: requirement
    element: ARM
    text: The arm controller shall clamp commanded speed to the configured limit.
    traces_to: SYS-1
    basis: derived
    why: SYS-1 needs a limit in the controller.
    reason: first requirement.
  - add: requirement
    element: ARM
    text: The arm controller shall keep working through a passing communication fault.
    traces_to: SYS-1
    basis: derived
    why: a dropped command must not leave the arm uncontrolled.
    reason: second requirement.
  - add: vi
    element: ARM
    verifies: [ARM-1]
    method: test
    technique: unit test
    description: Speed commands above 200 mm/s are clamped to 200 mm/s.
    tests:
      python: [tests/test_arm.py::test_clamp_at_200, tests/test_arm.py::test_slow_speed_passes_through]
    reason: covers the clamp.
YAML
spec lock SYS-1 --via chat --words "Locked the speed limit." >/dev/null
spec change close >/dev/null
git add -A; git commit -qm "Add the spec"

cp -r "$out/base" "$out/with-skill"; cd "$out/with-skill"
mkdir -p .claude/skills; cp -rL "$skill" .claude/skills/syseng
git add -A; git commit -qm "Add the skill"
