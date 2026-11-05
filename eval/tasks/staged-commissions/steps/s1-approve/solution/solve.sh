#!/bin/bash
# Oracle: builds all five stages at the first approval, in the house style, so
# the hidden check, the rule probe, and every static check can be confirmed on
# a known-good tree. Later steps' oracles change nothing.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
cp -R "$here/reference/src" /app/
cp "$here/reference/package.json" "$here/reference/package-lock.json" /app/
cd /app && npm ci --no-audit --no-fund
