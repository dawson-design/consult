#!/bin/bash
# Oracle: the simpler side of the fork. The fee rate is a named constant in the
# payouts module, with tests for the fee, its rounding, and the net totals.
# solution/other-side/ holds the other side (an environment variable) for the
# verifier tests; it is not applied here.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
cp -R "$here/files/." /app/
