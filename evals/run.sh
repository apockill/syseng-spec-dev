#!/usr/bin/env bash
# Runs this repository's evals of the skill, and records their results. Usage: evals/run.sh [repeats], from
# `nix develop .#evals`. It costs model usage: about $2 for the suite at three repeats.
set -euo pipefail
repeats=${1:-3}; here=$(realpath "$(dirname "$0")")
"$here/fixture.sh" "$here/.work/fixture"
[ -d "$here/node_modules" ] || (cd "$here" && npm ci --silent --no-audit --no-fund)
export CLAUDE_BIN; CLAUDE_BIN=$(realpath "$(command -v claude)")
PROMPTFOO_DISABLE_TELEMETRY=1 PROMPTFOO_DISABLE_UPDATE=1 "$here/node_modules/.bin/promptfoo" eval \
  -c "$here/promptfooconfig.yaml" --no-cache --no-progress-bar --repeat "$repeats" -j 4 -o "$here/.work/results.json" || true
spec results add "$here/.work/results.json" --format promptfoo --step evals
spec results status
