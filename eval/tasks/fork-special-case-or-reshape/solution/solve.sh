#!/bin/bash
# Oracle: the simpler side of the fork. Each payment method's behaviour moves
# into one lookup keyed by `method`, read at a single dispatch point, and bank
# transfers become its second entry. solution/other-side/ holds the other side
# (a bank check in each function) for the verifier tests; it is not applied here.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
cp -R "$here/files/." /app/
