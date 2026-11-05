#!/bin/bash
# Synced from eval/verifier/shared/brief_test.sh by eval/scripts/sync_tests.py. Do not edit here.
# Step-1 verifier. Harbor overlays this step's tests on the root tests/, so the
# step suite lives in its own directory and only it is scored here.
set -euo pipefail
cd /app
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
rewardkit /tests/brief_suite --workspace /app --output /logs/verifier/reward.json --max-concurrent-programmatic 1
