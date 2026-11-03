# Bash / shell review reference

Use when reviewing Bash, POSIX `sh`, or zsh scripts in the diff.

- A new non-trivial Bash script starts with `set -euo pipefail`.
- Run `shellcheck` on every changed script, even when CI does not run it.
  New warnings are findings, and each new `# shellcheck disable=SCxxxx`
  needs a one-line reason.
