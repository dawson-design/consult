#!/bin/bash
# Oracle: the simpler side of the fork. Response deadlines call the business-day
# rule where it already lives, in the delivery module, which now exports it.
# solution/other-side/ holds the other side (a second copy of the rule) for the
# verifier tests; it is not applied here.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
cp -R "$here/files/." /app/
