#!/usr/bin/env bash
# Runs the evals and records their results. Usage: evals/run.sh [repeats], from `nix develop .#evals`.
# It costs model usage: about $2 for the suite at three repeats.
set -euo pipefail
repeats=${1:-3}; here=$(realpath "$(dirname "$0")"); work=${EVALS_WORK:-$here/.work}; runner=$here/runners/promptfoo
mkdir -p "$work"
"$here/fixture.sh" "$work/fixture"
[ -d "$runner/node_modules" ] || (cd "$runner" && npm ci --silent --no-audit --no-fund)
python3 "$runner/build.py" "$here/evals.json" "$work" > "$work/promptfooconfig.yaml"
PROMPTFOO_DISABLE_TELEMETRY=1 PROMPTFOO_DISABLE_UPDATE=1 "$runner/node_modules/.bin/promptfoo" eval \
  -c "$work/promptfooconfig.yaml" --no-cache --no-progress-bar --repeat "$repeats" -j 4 -o "$work/results.json" || true
spec results add "$work/results.json" --format promptfoo --step evals
spec results status
