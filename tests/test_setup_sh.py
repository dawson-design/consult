"""setup.sh: preflight refusals and the interactive confirmation flow.

The confirmation tests drive setup.sh through Tcl `expect`. Without it they
cannot run at all, so they skip rather than fail as if setup.sh were broken.
CI installs `expect` so they do run there, and asserts nothing skipped.
"""

from __future__ import annotations

import json
import shutil
import unittest
from pathlib import Path

from helpers import ROOT, TempDirTestCase, env_with, run, write_executable

SETUP = ROOT / "setup.sh"

FAKE_STOW = """#!/bin/sh
set -eu
target=
while [ "$#" -gt 0 ]; do
  case "$1" in
    --target=*) target=${1#--target=} ;;
    --target) shift; target=$1 ;;
  esac
  shift || true
done
if [ -z "$target" ]; then
  echo "missing --target" >&2
  exit 2
fi
mkdir -p "$target/.agents/skills/testing"
printf '%s\\n' '---' 'name: testing' '---' > "$target/.agents/skills/testing/SKILL.md"
echo "LINK: .agents => test fixture"
"""

# setup.sh ends by running the plugin generator on this checkout. The fake
# records the call instead, so the tests never rewrite the real plugin/ tree.
FAKE_PYTHON = """#!/bin/sh
echo "$@" >> "$HOME/python3-invocations.log"
exit 0
"""

FAKE_AGY = """#!/bin/sh
echo "$@" >> "$HOME/agy-invocations.log"
exit 0
"""


def default_path(home: Path) -> str:
    """PATH with the fake tools in `home/bin` and only the system directories."""
    return f"{home / 'bin'}:/usr/bin:/bin"


def run_setup(home: Path, path: str | None = None):
    """Run setup.sh with no input, so every confirmation prompt reads EOF."""
    env = env_with(HOME=str(home), PATH=path or default_path(home))
    return run(["/bin/bash", SETUP], env=env)


def run_setup_interactively(home: Path, answers: str):
    """Run setup.sh under `expect`, typing `answers` (one line per prompt)."""
    # json.dumps yields a double-quoted string with backslash escapes, which
    # Tcl reads the same way.
    keystrokes = json.dumps(answers.replace("\n", "\r"))
    script = f"""
set timeout 5
spawn -noecho /bin/bash {SETUP}
send {keystrokes}
expect eof
catch wait result
exit [lindex $result 3]
"""
    env = env_with(HOME=str(home), PATH=default_path(home))
    return run(["expect", "-c", script], env=env)


class SetupPreflightTests(TempDirTestCase):
    # This test needs `stow` to be ABSENT: it pins PATH to /usr/bin:/bin and
    # asserts setup.sh refuses to proceed. Do not install GNU Stow on CI
    # runners; it would land in /usr/bin and break this assertion.
    def test_explains_missing_stow_without_touching_files(self) -> None:
        personal = self.tmp / "AGENTS.md"
        personal.write_text("# Personal\n\nDo not touch.\n", encoding="utf8")
        before = personal.read_text(encoding="utf8")
        before_mtime = personal.stat().st_mtime_ns

        result = run_setup(self.tmp, path="/usr/bin:/bin")

        self.assertEqual(result.returncode, 1)
        self.assertEqual(personal.read_text(encoding="utf8"), before)
        self.assertEqual(personal.stat().st_mtime_ns, before_mtime)
        self.assertNotIn("uv run", result.stderr)
        self.assertIn("GNU Stow is required", result.stderr)
        self.assertIn("brew install stow", result.stderr)
        self.assertFalse((self.tmp / ".agents").exists())

    def test_requires_confirmation_before_running_stow_or_touching_files(self) -> None:
        write_executable(self.tmp / "bin" / "stow", FAKE_STOW)

        result = run_setup(self.tmp)

        self.assertEqual(result.returncode, 1)
        for text in ["Consult setup will:", "run GNU Stow", "Google", "Antigravity", "Setup cancelled."]:
            self.assertIn(text, result.stdout)
        self.assertFalse((self.tmp / ".agents").exists())
        self.assertFalse((self.tmp / ".claude/skills").exists())
        self.assertFalse((self.tmp / ".codex/skills").exists())


@unittest.skipUnless(shutil.which("expect"), "needs Tcl expect")
class SetupConfirmationTests(TempDirTestCase):
    def setUp(self) -> None:
        super().setUp()
        write_executable(self.tmp / "bin" / "stow", FAKE_STOW)
        write_executable(self.tmp / "bin" / "python3", FAKE_PYTHON)

    def test_links_skills_and_installs_the_antigravity_plugin_after_confirmation(self) -> None:
        write_executable(self.tmp / "bin" / "agy", FAKE_AGY)
        (self.tmp / ".codex").mkdir()

        result = run_setup_interactively(self.tmp, "y\n")

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue((self.tmp / ".agents/skills/testing/SKILL.md").exists())
        self.assertTrue((self.tmp / ".claude/skills").is_symlink())
        self.assertTrue((self.tmp / ".codex/skills/testing").is_symlink())
        log = (self.tmp / "agy-invocations.log").read_text(encoding="utf8")
        self.assertEqual(log, f"plugin install {ROOT / 'plugin'}\n")
        self.assertFalse((self.tmp / ".codex/config.toml").exists())
        generator_calls = (self.tmp / "python3-invocations.log").read_text(encoding="utf8")
        self.assertEqual(generator_calls, f"{ROOT / 'scripts/generate_plugin_symlinks.py'} {ROOT}\n")

    def test_does_not_replace_conflicting_symlinks_without_interactive_confirmation(self) -> None:
        other = self.tmp / "other-skills/testing"
        other.mkdir(parents=True)
        conflict = self.tmp / ".codex/skills/testing"
        conflict.parent.mkdir(parents=True)
        conflict.symlink_to(other)

        result = run_setup_interactively(self.tmp, "y\nn\nn\n")

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("is a symlink to", result.stdout)
        self.assertEqual(conflict.readlink(), other)

    def test_does_not_move_real_directories_without_interactive_confirmation(self) -> None:
        target = self.tmp / ".codex/skills/testing"
        target.mkdir(parents=True)
        marker = target / "local.md"
        marker.write_text("personal skill\n", encoding="utf8")

        result = run_setup_interactively(self.tmp, "y\nn\nn\n")

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("exists as a real directory", result.stdout)
        self.assertEqual(marker.read_text(encoding="utf8"), "personal skill\n")

    def test_skips_the_antigravity_plugin_when_agy_is_not_installed(self) -> None:
        result = run_setup_interactively(self.tmp, "y\n")

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("Google Antigravity (agy) not installed", result.stdout)
        self.assertFalse((self.tmp / "agy-invocations.log").exists())


if __name__ == "__main__":
    unittest.main()
