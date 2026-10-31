"""Shared helpers for the repo maintenance tests in tests/.

Run the suite with `python3 -m unittest discover -s tests`. Each test module
drives a maintenance script or shell script through its command line, so the
tests describe what a maintainer sees rather than how the script is built.
"""

from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run(
    args: list[str | Path],
    *,
    cwd: Path = ROOT,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run a command and capture its text output without raising on failure.

    Args:
        args: the program and its arguments.
        cwd: working directory, the repo root by default.
        env: the full environment, or None to inherit this process's.

    Returns:
        The completed process, whatever its exit status.

    Raises:
        FileNotFoundError: the program is not installed. Letting this escape
            keeps "the tool is missing" from looking like a failing check.
    """
    return subprocess.run(
        [str(arg) for arg in args],
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def env_with(**overrides: str) -> dict[str, str]:
    """Return a copy of this process's environment with `overrides` applied."""
    return {**os.environ, **overrides}


def write_executable(path: Path, text: str) -> None:
    """Write `text` to `path` and mark it executable, creating parent directories."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf8")
    path.chmod(0o755)


class TempDirTestCase(unittest.TestCase):
    """Test case that gives each test a fresh temporary directory as `self.tmp`.

    The directory and everything in it is removed after the test.
    """

    def setUp(self) -> None:
        temp = tempfile.TemporaryDirectory(prefix="consult-test-")
        self.addCleanup(temp.cleanup)
        # Resolve so paths match what child processes report on macOS, where
        # the temp dir sits behind the /var -> /private/var symlink.
        self.tmp = Path(temp.name).resolve()
