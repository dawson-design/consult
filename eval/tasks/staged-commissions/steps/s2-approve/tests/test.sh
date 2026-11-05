#!/bin/bash
# Synced from eval/verifier/shared/step_test.sh by eval/scripts/sync_tests.py. Do not edit here.
# Verifier for a step between the first and the last. The trial reward is the
# final step's, so this step records a placeholder instead of running the
# shared verifier and its judge after every approval turn.
set -euo pipefail
mkdir -p /logs/verifier
# Snapshot the workspace as this step left it, numbered by step (0-based), for
# per-stage scores at the end of a staged task. node_modules is linked, not
# copied. Called in an || list, so a failure here never stops the reward below.
snapshot() {
  local root=/opt/eval/snapshots n
  mkdir -p "$root"
  n=$(find "$root" -mindepth 1 -maxdepth 1 | wc -l | tr -d ' ')
  mkdir -p "$root/$n"
  tar -C /app --exclude=./node_modules --exclude=./.git -cf - . | tar -C "$root/$n" -xf -
  if [ -d /app/node_modules ]; then ln -s /app/node_modules "$root/$n/node_modules"; fi
}
snapshot || echo "consult: workspace snapshot failed" >&2
echo 0 > /logs/verifier/reward.txt
