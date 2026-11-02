"""The skills-page generator: parsing core.md, the README skill list, and Iron Laws, and the
guard that every skill directory appears on the page.

The last test runs the real sources, so a skill added without a README entry, or a page left
stale after a source change, fails here as well as in `--check`.
"""

from __future__ import annotations

import importlib.util
import sys
import unittest

from helpers import ROOT

SPEC = importlib.util.spec_from_file_location("build_site_skills", ROOT / "scripts/build_site_skills.py")
bss = importlib.util.module_from_spec(SPEC)
sys.modules["build_site_skills"] = bss  # dataclasses look the module up while it loads
SPEC.loader.exec_module(bss)

CORE = """# Consult core

## Iron Law

`KEEP IT SIMPLE.`

## Rules

1. **First rule.** Sentence one. Sentence two
   continues here.
2. **Second rule** continues the title, even here. More.
"""

README = """# X

## Skills

Intro.

- Group A:
  - [`alpha`](agents/.agents/skills/alpha/SKILL.md): Does `alpha` things.
- Group B:
  - [`beta`](agents/.agents/skills/beta/SKILL.md): Does beta things.

## Next
"""


class ParseCoreTest(unittest.TestCase):
    """parse_core returns the Iron Law and each rule's title and first sentence."""

    def test_iron_law_and_rules(self) -> None:
        iron, rules = bss.parse_core(CORE)
        self.assertEqual(iron, "KEEP IT SIMPLE.")
        self.assertEqual(
            [(r.number, r.title, r.first_sentence) for r in rules],
            [
                (1, "First rule.", "Sentence one."),
                (2, "Second rule", "continues the title, even here."),
            ],
        )

    def test_missing_iron_law_is_an_error(self) -> None:
        with self.assertRaises(ValueError):
            bss.parse_core("## Rules\n\n1. **A.** b.\n")


class ReadmeSkillsTest(unittest.TestCase):
    """parse_readme_skills keeps the README's groups and order."""

    def test_groups_and_items(self) -> None:
        self.assertEqual(
            bss.parse_readme_skills(README),
            [
                ("Group A", [("alpha", "Does `alpha` things.")]),
                ("Group B", [("beta", "Does beta things.")]),
            ],
        )


class RenderTest(unittest.TestCase):
    """Rendering escapes text, renders code spans, and joins continuing rule titles."""

    def test_inline_escapes_then_renders_code(self) -> None:
        self.assertEqual(bss.inline("a < b `c`"), "a &lt; b <code>c</code>")

    def test_sentence_case_keeps_acronyms(self) -> None:
        self.assertEqual(
            bss.sentence_case("WRITE THE OPENAPI SPEC FIRST. NO PII IN LOGS; WCAG 2.2 AA."),
            "Write the OpenAPI spec first. No PII in logs; WCAG 2.2 AA.",
        )

    def test_joiner(self) -> None:
        self.assertEqual(bss.joiner(", even"), "")
        self.assertEqual(bss.joiner("Then"), " ")


class RealSourcesTest(unittest.TestCase):
    """The real repo sources build, list every skill, and match the page on disk."""

    def test_every_skill_listed_and_page_current(self) -> None:
        page = bss.build()
        skills = sorted(p.parent.name for p in bss.SKILLS_DIR.glob("*/SKILL.md"))
        for name in skills:
            self.assertIn(f"<code>{name}</code></a></dt>", page)
        self.assertEqual(page, bss.OUT.read_text(encoding="utf-8"), "run scripts/build_site_skills.py")


if __name__ == "__main__":
    unittest.main()
