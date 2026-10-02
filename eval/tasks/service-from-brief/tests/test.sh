#!/bin/bash
# Synced from eval/verifier/shared/test.sh by eval/scripts/sync_tests.py. Do not edit here.
set -euo pipefail
cd /app
mkdir -p /logs/verifier
python3 /tests/consult_lib.py bundle > /logs/verifier/judge-bundle.md
# prepare inlines the bundle into the judge prompt, so it runs after bundle.
python3 /tests/consult_lib.py prepare /tests
# The claude-code judge ignores quality.toml's reasoning_effort; its CLI reads this.
export CLAUDE_CODE_EFFORT_LEVEL=low
# One programmatic criterion at a time: several start servers or run npm in /app.
rewardkit /tests --workspace /app --output /logs/verifier/reward.json --max-concurrent-programmatic 1
