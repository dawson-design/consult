"""The shipped plugin SessionStart hook, end to end.

Runs the hook's command the way a host does and compares the output with
its source, agents/.agents/core.md.
"""

from __future__ import annotations

import json
import re
import unittest

from helpers import ROOT, load_script, run

generator = load_script("generate_plugin_symlinks")
HOOK_SOURCE = generator.HOOK_SOURCE
HOOK_DEST = generator.HOOK_DEST

# The routing paragraph comes first so it survives if a host truncates hook
# output; keeping it short keeps that guarantee cheap.
MAX_ROUTING_CHARS = 400


def session_start_command() -> str:
    """Return the single SessionStart command from plugin/hooks/hooks.json."""
    hooks_file = json.loads((ROOT / HOOK_DEST).read_text(encoding="utf8"))
    return hooks_file["hooks"]["SessionStart"][0]["hooks"][0]["command"]


class PluginSessionHookTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.result = run(["sh", "-c", session_start_command()])

    def test_prints_core_md_exactly_ending_in_one_newline(self) -> None:
        core = (ROOT / HOOK_SOURCE).read_text(encoding="utf8").replace("\r", "").strip()

        self.assertEqual(self.result.returncode, 0, self.result.stderr)
        self.assertEqual(self.result.stdout, f"{core}\n")

    def test_opens_with_a_short_routing_paragraph_that_names_a_skill_the_plugin_ships(self) -> None:
        routing = self.result.stdout.strip().split("\n\n")[0]

        # eval/scripts/triggers.py detects the hook by this phrase.
        self.assertTrue(routing.startswith("Consult is installed."))
        self.assertLessEqual(len(routing), MAX_ROUTING_CHARS)
        named = re.search(r"consult:([a-z][a-z0-9-]*) skill", routing)
        self.assertIsNotNone(named, "routing paragraph names no Consult skill")
        self.assertTrue((ROOT / "plugin/skills" / named[1] / "SKILL.md").exists())


if __name__ == "__main__":
    unittest.main()
