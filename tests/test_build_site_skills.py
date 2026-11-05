"""The skills page generator reads core.md and the skills' frontmatter, and the page on disk is current."""

from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path

import build_site_skills as bss

ROOT = Path(__file__).resolve().parents[1]

CORE = """Consult is installed.

# Consult core

Complexity is the enemy: keep software
simple.

## Rules

1. Keep calculations apart. A function reads
   no clock.
2. Build only what was asked.

## House defaults

Where several approaches are sound, use these.

1. **Paradigm:** functional core.
4. **Errors:** return `Result` values.

## Working with the human

The engineer stays in the loop.

1. A feature has two checkpoints:
   - **Plan.** Agree the design
     direction.
   - **Data and contracts.** Show the shapes.

   A fix skips both.
2. Stop and ask before a migration.
"""


class ParseCoreTest(unittest.TestCase):
    """parse_core reads the principle and each section's intro and numbered items."""

    def setUp(self) -> None:
        self.core = bss.parse_core(CORE)

    def test_principle_joins_its_wrapped_lines(self) -> None:
        self.assertEqual(self.core.principle, "Complexity is the enemy: keep software simple.")

    def test_rules_join_wrapped_lines(self) -> None:
        rules = self.core.sections["Rules"].items
        self.assertEqual([r.number for r in rules], [1, 2])
        self.assertEqual(rules[0].blocks, ("Keep calculations apart. A function reads no clock.",))

    def test_defaults_keep_their_numbers_and_intro(self) -> None:
        defaults = self.core.sections["House defaults"]
        self.assertEqual(defaults.intro, "Where several approaches are sound, use these.")
        self.assertEqual([d.number for d in defaults.items], [1, 4])

    def test_an_item_keeps_its_bullets_and_later_paragraph(self) -> None:
        first = self.core.sections["Working with the human"].items[0]
        bullets = ("**Plan.** Agree the design direction.", "**Data and contracts.** Show the shapes.")
        self.assertEqual(first.blocks, ("A feature has two checkpoints:", bullets, "A fix skips both."))

    def test_a_missing_section_is_an_error(self) -> None:
        with self.assertRaisesRegex(ValueError, "House defaults"):
            bss.parse_core(CORE.replace("## House defaults", "## Other"))


class RenderTest(unittest.TestCase):
    """Rendering escapes HTML and keeps each item's own number."""

    def test_inline_escapes_then_renders_code_and_bold(self) -> None:
        self.assertEqual(bss.inline("**Tooling:** `a<b` & c"), "<b>Tooling:</b> <code>a&lt;b</code> &amp; c")

    def test_an_item_keeps_a_skipped_number(self) -> None:
        item = bss.Item(4, ("Errors.", ("one", "two"), "Then this."))
        expected = '<li value="4">Errors.<ul><li>one</li><li>two</li></ul><p>Then this.</p></li>'
        self.assertEqual(bss.render_item(item), expected)

    def test_frontmatter_flags_an_invoked_only_skill(self) -> None:
        text = '---\nname: release\ndescription: "Prepares a release."\ndisable-model-invocation: true\n---\n'
        fields = bss.parse_frontmatter(text)
        self.assertEqual(fields["description"], "Prepares a release.")
        self.assertEqual(fields["disable-model-invocation"], "true")

    def test_iron_law_is_the_paragraph_under_its_heading(self) -> None:
        text = "---\nname: api\n---\n\n# API\n\n## Iron law\n\nWrite the spec\nfirst.\n\n## Rules\n"
        self.assertEqual(bss.iron_law(text), "Write the spec first.")
        self.assertIsNone(bss.iron_law("# API\n\n## Rules\n"))


class RealSourcesTest(unittest.TestCase):
    """The committed page matches what the generator builds from the repo's sources."""

    def test_page_is_current(self) -> None:
        result = subprocess.run(
            [sys.executable, str(ROOT / "scripts/build_site_skills.py"), "--check"],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
