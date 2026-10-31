"""scripts/update-installed-plugins.sh: the plugin update commands it runs or prints.

Fake agent CLIs on PATH log each invocation, so the tests see exactly what
the script would run against the real harnesses.
"""

from __future__ import annotations

import unittest
from pathlib import Path

from helpers import ROOT, TempDirTestCase, env_with, run, write_executable

SCRIPT = ROOT / "scripts/update-installed-plugins.sh"
AGENT_CLIS = ["claude", "codex", "pi", "agy", "cursor"]


def make_fake_agent_bin(home: Path) -> Path:
    """Create logging stand-ins for every agent CLI and return their directory."""
    bin_dir = home / "bin"
    for name in AGENT_CLIS:
        write_executable(
            bin_dir / name,
            f"""#!/bin/sh
set -eu
printf '%s %s\\n' "{name}" "$*" >> "$HOME/agent-plugin-updates.log"
""",
        )
    return bin_dir


class UpdateInstalledPluginsTests(TempDirTestCase):
    def run_script(self, *args: str):
        bin_dir = make_fake_agent_bin(self.tmp)
        env = env_with(HOME=str(self.tmp), PATH=f"{bin_dir}:/usr/bin:/bin")
        return run(["/bin/bash", SCRIPT, *args], env=env)

    def test_prints_official_agent_harness_update_commands_in_dry_run_mode(self) -> None:
        result = self.run_script("--dry-run")

        self.assertEqual(result.returncode, 0, result.stderr)
        for text in [
            "claude plugin marketplace add dawson-design/consult",
            "claude plugin install consult@consult",
            "claude plugin update consult@consult",
            "codex plugin marketplace add dawson-design/consult",
            "codex plugin marketplace upgrade consult",
            "codex plugin add consult@consult",
            "agy plugin install",
            "cursor agent --print",
        ]:
            self.assertIn(text, result.stdout)
        self.assertNotIn("pi install", result.stdout)
        self.assertNotIn("cp -R", result.stdout)
        self.assertFalse((self.tmp / "agent-plugin-updates.log").exists())

    def test_runs_plugin_update_commands_through_installed_agent_clis(self) -> None:
        result = self.run_script()

        self.assertEqual(result.returncode, 0, result.stderr)
        log = (self.tmp / "agent-plugin-updates.log").read_text(encoding="utf8")
        for text in [
            "claude plugin marketplace add dawson-design/consult",
            "claude plugin marketplace update consult",
            "claude plugin install consult@consult",
            "claude plugin update consult@consult",
            "codex plugin marketplace add dawson-design/consult",
            "codex plugin marketplace upgrade consult",
            "codex plugin add consult@consult",
            f"agy plugin install {ROOT / 'plugin'}",
            "cursor agent --print Update the Consult plugin",
        ]:
            self.assertIn(text, log)
        self.assertNotIn("pi install", log)


if __name__ == "__main__":
    unittest.main()
