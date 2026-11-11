#!/usr/bin/env bash
# Runs this repository's evals of the skill, and records their results. Usage: evals/run.sh [repeats] [suite ...],
# from `nix develop .#evals`. The suites are promptfooconfig (the default cases) and requirements (writing
# requirements for a whole project, much longer); both run when none is named. SKILL_BASELINE=<git ref> gives the
# requirements suite's baseline arm the skill as it was at that ref, to compare two versions in one batch.
# EVAL_JOBS sets how many runs go at once (default 4).
set -euo pipefail
repeats=${1:-3}; shift || true; here=$(realpath "$(dirname "$0")")
suites=("$@"); [ ${#suites[@]} -gt 0 ] || suites=(promptfooconfig requirements)
"$here/fixture.sh" "$here/.work/fixture"
"$here/lampboard.sh" "$here/.work/lampboard" "${SKILL_BASELINE:-}"
[ -d "$here/node_modules" ] || (cd "$here" && npm ci --silent --no-audit --no-fund)
export CLAUDE_BIN; CLAUDE_BIN=$(realpath "$(command -v claude)")
reports=()
for suite in "${suites[@]}"; do
  PROMPTFOO_DISABLE_TELEMETRY=1 PROMPTFOO_DISABLE_UPDATE=1 "$here/node_modules/.bin/promptfoo" eval \
    -c "$here/$suite.yaml" --no-cache --no-progress-bar --repeat "$repeats" -j "${EVAL_JOBS:-4}" -o "$here/.work/$suite.json" || true
  reports+=("$here/.work/$suite.json")
done
spec results add "${reports[@]}" --format promptfoo --step evals
spec results status
