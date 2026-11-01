"""The pre-commit acceptance script: which checks it selects, and its CLI.

Each test runs the script with `--dry-run` against a scratch git repo, so
the selected checks are read from what the script prints, not from its
internals.
"""

from __future__ import annotations

import os
import unittest
from pathlib import Path

from helpers import ROOT, TempDirTestCase, run

COMMAND = ["python3", ROOT / "scripts/pre_commit_acceptance.py"]


def clean_env() -> dict[str, str]:
    """This process's environment without GIT_* variables.

    Inside a git hook, GIT_DIR and GIT_INDEX_FILE point at the real repo, and
    the scratch-repo commands below would act on it instead.
    """
    return {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}


def git(repo: Path, *args: str) -> None:
    """Run a git command in `repo`, failing the test setup if it fails."""
    result = run(["git", *args], cwd=repo, env=clean_env())
    if result.returncode != 0:
        raise RuntimeError(result.stderr)


class CheckSelectionTests(TempDirTestCase):
    def dry_run_with_staged(self, *names: str) -> str:
        git(self.tmp, "init", "-q", "-b", "topic")
        for name in names:
            (self.tmp / name).write_text("text\n", encoding="utf8")
        git(self.tmp, "add", *names)
        result = run([*COMMAND, "--repo-root", self.tmp, "--dry-run"], env=clean_env())
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout

    def test_always_checks_the_staged_diff(self) -> None:
        self.assertIn("==> git diff --cached --check", self.dry_run_with_staged("notes.txt"))

    def test_checks_markdown_when_markdown_files_are_staged(self) -> None:
        self.assertIn("==> make links", self.dry_run_with_staged("README.md"))

    def test_skips_the_markdown_check_when_no_markdown_is_staged(self) -> None:
        self.assertNotIn("make links", self.dry_run_with_staged("notes.txt"))

    def test_lints_and_format_checks_python_when_python_files_are_staged(self) -> None:
        output = self.dry_run_with_staged("tool.py")

        self.assertIn("==> uv run --locked ruff check", output)
        self.assertIn("==> uv run --locked ruff format --check", output)

    def test_skips_the_python_checks_when_no_python_is_staged(self) -> None:
        self.assertNotIn("ruff", self.dry_run_with_staged("README.md"))


class PreCommitCliTests(TempDirTestCase):
    def test_allows_dry_run_checks_on_main(self) -> None:
        git(self.tmp, "init", "-q", "-b", "main")

        result = run([*COMMAND, "--repo-root", self.tmp, "--dry-run"], env=clean_env())

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("No staged files; nothing to validate.", result.stdout)

    def test_reports_no_staged_files_on_topic_branches(self) -> None:
        git(self.tmp, "init", "-q", "-b", "chore/test")

        result = run([*COMMAND, "--repo-root", self.tmp, "--dry-run"], env=clean_env())

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("No staged files; nothing to validate.", result.stdout)


if __name__ == "__main__":
    unittest.main()
