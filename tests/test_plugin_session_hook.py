"""The plugin SessionStart hook: the routing line every host adds to context."""

from __future__ import annotations

import json
import re
import unittest

from helpers import ROOT, run

# Every host adds this output to each session's context, so it stays small.
MAX_ROUTING_CHARS = 400


def session_start_command() -> str:
    """Return the single SessionStart command from plugin/hooks/hooks.json."""
    hooks_file = json.loads((ROOT / "plugin/hooks/hooks.json").read_text(encoding="utf8"))
    return hooks_file["hooks"]["SessionStart"][0]["hooks"][0]["command"]


class PluginSessionHookTests(unittest.TestCase):
    def test_prints_a_short_routing_line_that_names_a_skill_the_plugin_ships(self) -> None:
        result = run(["sh", "-c", session_start_command()])

        self.assertEqual(result.returncode, 0, result.stderr)
        routing = result.stdout.strip()
        self.assertGreater(len(routing), 0)
        self.assertLessEqual(len(routing), MAX_ROUTING_CHARS)
        named = re.search(r"consult:([a-z][a-z0-9-]*) skill", routing)
        self.assertIsNotNone(named, "routing line names no Consult skill")
        self.assertTrue((ROOT / "plugin/skills" / named[1] / "SKILL.md").exists())


if __name__ == "__main__":
    unittest.main()
