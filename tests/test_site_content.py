"""The marketing site's hand-written facts match the repo, and site/ holds only the shipped pages.

The home page (site/index.html) states the skill count, the core-rule count, and the release
version in prose. These tests read the real sources (skill directories, core.md, and the plugin
manifests) so a release or a new skill cannot leave the page quietly wrong. The file check stops
draft or stale pages being published to GitHub Pages.
"""

from __future__ import annotations

import json
import re
import unittest

from helpers import ROOT

SITE = ROOT / "site"
HOME = (SITE / "index.html").read_text(encoding="utf-8")
SHIPPED_PAGES = {"index.html", "skills/index.html"}
NUMBER_WORDS = {
    7: "Seven",
    8: "Eight",
    9: "Nine",
    10: "Ten",
    11: "Eleven",
    12: "Twelve",
}


def skill_count() -> int:
    """Number of canonical skills (directories holding a SKILL.md)."""
    return len(list((ROOT / "agents/.agents/skills").glob("*/SKILL.md")))


def core_rule_count() -> int:
    """Number of numbered rules in the Consult core."""
    text = (ROOT / "agents/.agents/core.md").read_text(encoding="utf-8")
    return len(re.findall(r"^\d+\.\s+\*\*", text, re.MULTILINE))


def release_version() -> str:
    """The pack version from the Claude Code marketplace manifest."""
    manifest = json.loads((ROOT / ".claude-plugin/marketplace.json").read_text(encoding="utf-8"))
    return manifest["metadata"]["version"]


class HomePageFactsTest(unittest.TestCase):
    """Counts and the release line on the home page match their sources."""

    def test_skill_and_rule_counts(self) -> None:
        self.assertIn(f"{skill_count()} skills, {core_rule_count()} core rules", HOME)

    def test_core_rule_count_in_words(self) -> None:
        word = NUMBER_WORDS.get(core_rule_count())
        self.assertIsNotNone(word, "extend NUMBER_WORDS for the new core-rule count")
        self.assertIn(f"{word} core rules", HOME)

    def test_release_line_and_changelog_anchor(self) -> None:
        version = release_version()
        self.assertIn(f">Release {version}</a>", HOME)
        anchor = re.search(r'CHANGELOG\.md#([\w-]+)">Release', HOME)
        self.assertIsNotNone(anchor, "the release line should link to its changelog entry")
        heading = re.search(
            rf"^## \[{re.escape(version)}\] \(([\d-]+)\)",
            (ROOT / "CHANGELOG.md").read_text(encoding="utf-8"),
            re.MULTILINE,
        )
        self.assertIsNotNone(heading, f"CHANGELOG.md has no {version} entry")
        self.assertEqual(anchor[1], version.replace(".", "") + "-" + heading[1])


class ShippedFilesTest(unittest.TestCase):
    """site/ contains only the pages that are meant to be published."""

    def test_only_shipped_pages(self) -> None:
        pages = {p.relative_to(SITE).as_posix() for p in SITE.rglob("*.html")}
        self.assertEqual(pages, SHIPPED_PAGES)


if __name__ == "__main__":
    unittest.main()
