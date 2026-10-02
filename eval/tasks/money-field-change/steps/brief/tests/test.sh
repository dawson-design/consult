#!/bin/bash
# Synced from eval/verifier/shared/brief_test.sh by eval/scripts/sync_tests.py. Do not edit here.
# Step-1 verifier. Harbor overlays this step's tests on the root tests/, so the
# step suite lives in its own directory and only it is scored here.
set -euo pipefail
cd /app
mkdir -p /logs/verifier
rewardkit /tests/brief_suite --workspace /app --output /logs/verifier/reward.json --max-concurrent-programmatic 1
