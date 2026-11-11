#!/bin/bash
# Verifier for a follow-up task that scripts/followup.py builds. It scores only
# what Consult did not define: the visible tests and the hidden check (stages 1
# to 5 unchanged, plus the follow-up change). judge-bundle.md records the change
# against the starting tree, from which followup.py report counts files and lines.
set -euo pipefail
cd /app
mkdir -p /logs/verifier
python3 /tests/consult_lib.py bundle > /logs/verifier/judge-bundle.md
rewardkit /tests --workspace /app --output /logs/verifier/reward.json --max-concurrent-programmatic 1
