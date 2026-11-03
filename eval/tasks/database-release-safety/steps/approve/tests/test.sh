#!/bin/bash
# Synced from eval/verifier/shared/step_test.sh by eval/scripts/sync_tests.py. Do not edit here.
# Verifier for a step between the first and the last. The trial reward is the
# final step's, so this step records a placeholder instead of running the
# shared verifier and its judge after every approval turn.
set -euo pipefail
mkdir -p /logs/verifier
echo 0 > /logs/verifier/reward.txt
