# Bash / shell review reference

Use when reviewing Bash, POSIX `sh`, or zsh scripts in the diff.
Apply this alongside the main `code-review` skill workflow.

## Tooling that should be passing

- `shellcheck <script>`: non-negotiable. Warnings introduced by the
  diff are findings; new `# shellcheck disable=SCxxxx` comments need
  a one-line reason.
- `shfmt -d -i 2 -ci <script>` (or the project's chosen indent) for
  formatting.
- The script's shebang must match the syntax it actually uses. Bash
  features under `#!/bin/sh` is a Critical finding.

## High-signal review checks

- Strict mode: every script that isn't a tiny one-liner should
  start with `set -euo pipefail` and a sane `IFS`. Missing it on a
  new script is a finding.
  - `-e`: exit on error. It does not fire inside `if`/`while`
    tests, `&&`/`||` lists, functions called from those, or
    `$(...)` without `inherit_errexit`: check those explicitly.
  - `-u`: unset variables are errors.
  - `-o pipefail`: catch failures inside pipelines.
- Quoting: every `$var` and `$(cmd)` expansion that could
  contain spaces, globs, or empty strings must be quoted. Unquoted
  expansion is the most common source of subtle bash bugs.
- Test syntax: prefer `[[ ... ]]` (bash) over `[ ... ]`. Never
  use `[[` under `#!/bin/sh`.
- `local` for function variables: Bash function variables that
  are not declared `local` leak into the caller's scope.
- Cleanup: any `mktemp` / temp directory needs a `trap '...'
  EXIT` cleanup. Long-running scripts also need `trap` on `INT` /
  `TERM` to clean up on cancellation.
- No parsing `ls`: globbing, `find -print0 | xargs -0`, or
  `for f in *.ext` are correct; `for f in $(ls)` is not.
- Argument passthrough: prefer `"$@"` over `$*`; pass arrays as
  arrays, not as space-joined strings.
- Idempotency: scripts that create directories, set state, or
  symlink should be safe to run twice. `mkdir -p`, `ln -snf`,
  conditional `if [ ! -e path ]` are the basic moves.
- Error messages to stderr: `echo "error: ..." >&2` not stdout,
  so callers can capture stdout cleanly.
- Subshell traps: traps don't propagate into subshells; a
  pipeline like `cmd | filter` runs `cmd` in a subshell on most
  shells.
- Exit codes: explicit `exit 1` / `exit 2` for distinct error
  classes; don't rely on the last command's exit code unless the
  script is a one-liner.
- `eval`: `eval` on anything derived from outside input is a
  Critical injection finding. Almost always avoidable with arrays.
  `bash -c` with interpolated input is the same injection: pass data
  as positional args (`bash -c 'cmd "$1"' _ "$arg"`).

## Anti-patterns / red flags

- Missing `set -euo pipefail` on a non-trivial script.
- Unquoted `$variable` expansions.
- `for f in $(ls dir)`.
- `eval` on a constructed string.
- `cd $dir` without checking the result, then doing destructive work.
- `rm -rf "$VAR/"` where `$VAR` could be empty (`rm -rf "/"`).
- `[ "$x" = "" ]`: prefer `[ -z "$x" ]` and quote.
- Deeply nested pipelines that hide a failed step due to no
  `pipefail`.
- `#!/bin/sh` with bashisms (`[[`, arrays, `function` keyword).

## Sources

- ShellCheck wiki:
  <https://www.shellcheck.net/wiki/>
- Google Shell Style Guide:
  <https://google.github.io/styleguide/shellguide.html>
- Bash Pitfalls (Greg's wiki): <http://mywiki.wooledge.org/BashPitfalls>
- BashFAQ: <http://mywiki.wooledge.org/BashFAQ>
