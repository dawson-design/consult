#!/usr/bin/env python3
"""Run deterministic Consult pre-commit checks for staged diffs, Markdown, and Python.

.githooks/pre-commit runs this script. It picks checks from the staged file
list, so a commit pays only for the checks its files need. Stdlib only, so it
runs with a bare python3.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import NamedTuple

USAGE = """Usage: python3 scripts/pre_commit_acceptance.py [--repo-root PATH] [--dry-run]

Run Consult pre-commit checks for staged files."""


class Check(NamedTuple):
    """One command to run, why it runs, and the tools it needs on PATH."""

    reason: str
    command: list[str]
    required_tools: tuple[str, ...] = ()


class Args(NamedTuple):
    """Parsed command line: the repo to check, and whether to only list the checks."""

    repo_root: str
    dry_run: bool


def repo_root_from_script() -> str:
    """Return the repository root: the parent of this script's directory."""
    return str(Path(__file__).resolve().parent.parent)


def run_git(root: str, *args: str) -> subprocess.CompletedProcess[str]:
    """Run git in `root` and capture its text output without raising on failure."""
    return subprocess.run(["git", *args], cwd=root, capture_output=True, text=True, check=False)


def current_branch(root: str) -> str:
    """Return the checked-out branch name, or "" when HEAD is detached or git fails."""
    result = run_git(root, "branch", "--show-current")
    return result.stdout.strip() if result.returncode == 0 else ""


def staged_paths(root: str) -> list[str]:
    """Return the staged paths that were added, copied, modified, renamed, or deleted.

    Raises:
        RuntimeError: git could not list the staged files.
    """
    result = run_git(root, "diff", "--cached", "--name-only", "--diff-filter=ACMRD")
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "could not inspect staged files")
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def select_checks(paths: list[str]) -> list[Check]:
    """Return the checks the staged `paths` need.

    The whitespace check always runs. Markdown adds the link check, and Python
    adds ruff's lint and format checks (the same commands as `make lint`).
    """
    checks = [Check("staged diff has no whitespace errors", ["git", "diff", "--cached", "--check"])]
    if any(path.endswith(".md") for path in paths):
        checks.append(Check("Markdown parses and local links resolve", ["pnpm", "run", "check:links"], ("pnpm",)))
    if any(path.endswith(".py") for path in paths):
        checks.append(Check("Python passes ruff lint", ["uv", "run", "--locked", "ruff", "check"], ("uv",)))
        checks.append(
            Check("Python is ruff-formatted", ["uv", "run", "--locked", "ruff", "format", "--check"], ("uv",))
        )
    return checks


def missing_tools(check: Check) -> list[str]:
    """Return the tools `check` needs that are not on PATH."""
    return [tool for tool in check.required_tools if shutil.which(tool) is None]


def run_check(root: str, check: Check, dry_run: bool) -> bool:
    """Announce `check`, then run it unless `dry_run`; return whether it passed.

    A check whose tools are missing fails without running.
    """
    print(f"==> {' '.join(check.command)}")
    print(f"    {check.reason}", flush=True)
    missing = missing_tools(check)
    if missing:
        print(f"ERROR: missing required tool(s): {', '.join(missing)}", file=sys.stderr)
        return False
    if dry_run:
        return True
    result = subprocess.run(check.command, cwd=root, check=False)
    if result.returncode != 0:
        print(f"ERROR: command failed with exit code {result.returncode}", file=sys.stderr)
        return False
    return True


def run_checks(root: str, checks: list[Check], dry_run: bool) -> int:
    """Run every check, so one failure does not hide another; return 1 when any failed, else 0."""
    results = [run_check(root, check, dry_run) for check in checks]
    return 0 if all(results) else 1


def parse_args(argv: list[str]) -> Args | int:
    """Parse `argv` into Args, or return the exit code: 0 after printing help, 2 for an unknown option."""
    repo_root = repo_root_from_script()
    dry_run = False
    index = 0
    while index < len(argv):
        arg = argv[index]
        if arg in {"-h", "--help"}:
            print(USAGE)
            return 0
        if arg == "--dry-run":
            dry_run = True
        elif arg == "--repo-root":
            repo_root = argv[index + 1]
            index += 1
        else:
            print(f"ERROR: unknown option: {arg}", file=sys.stderr)
            return 2
        index += 1
    return Args(os.path.abspath(repo_root), dry_run)


def main(argv: list[str]) -> int:
    """Run the CLI on `argv` (arguments after the program name) and return the exit code.

    Returns 0 when every check passes or nothing is staged, 1 when a check
    fails, and 2 for a bad option, a missing repo root, or a git failure.
    """
    args = parse_args(argv)
    if isinstance(args, int):
        return args
    root = args.repo_root
    if not os.path.isdir(root):
        print(f"ERROR: repo root is not a directory: {root}", file=sys.stderr)
        return 2
    branch = current_branch(root)
    try:
        paths = staged_paths(root)
    except RuntimeError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2
    if not paths:
        print("No staged files; nothing to validate.")
        return 0
    print("Consult pre-commit checks")
    print(f"Branch: {branch or '(detached HEAD)'}")
    print("Staged files:")
    for path in paths:
        print(f"  - {path}")
    return run_checks(root, select_checks(paths), args.dry_run)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
