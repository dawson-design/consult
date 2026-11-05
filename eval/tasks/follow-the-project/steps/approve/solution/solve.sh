#!/bin/bash
# Oracle: gift cards built the way this project already builds features:
# layer folders, classes, thrown AppErrors, and a test in test/.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
cp -R "$here/files/." /app/
