"""The marketing site's hand-written facts match the repo, and site/ holds only the shipped pages.

The home page (site/index.html) states the skill count and the core-rule count in prose, the
essay (site/why/index.html) quotes the Iron Law, and the evidence page (site/evidence/index.html)
reports eval figures from eval/results/2026-11-04-houseStyle.json. These tests read the real
sources (skill directories and core.md) so a release or a new skill cannot leave the page quietly
wrong. The file check stops draft or stale pages being published to GitHub Pages.
"""

from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

import build_site_skills

ROOT = Path(__file__).resolve().parents[1]

SITE = ROOT / "site"
HOME = (SITE / "index.html").read_text(encoding="utf-8")
WHY = (SITE / "why/index.html").read_text(encoding="utf-8")
EVIDENCE = (SITE / "evidence/index.html").read_text(encoding="utf-8")
CORE = build_site_skills.parse_core((ROOT / "agents/.agents/core.md").read_text(encoding="utf-8"))
RESULTS = json.loads((ROOT / "eval/results/2026-11-04-houseStyle.json").read_text(encoding="utf-8"))
SHIPPED_PAGES = {"index.html", "skills/index.html", "why/index.html", "evidence/index.html"}
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
    """Number of numbered items under the Consult core's `## Rules`."""
    return len(CORE.sections["Rules"].items)


class HomePageFactsTest(unittest.TestCase):
    """The counts on the home page match their sources."""

    def test_skill_and_rule_counts(self) -> None:
        self.assertIn(f"{skill_count()} skills, {core_rule_count()} core rules", HOME)

    def test_core_rule_count_in_words(self) -> None:
        word = NUMBER_WORDS.get(core_rule_count())
        self.assertIsNotNone(word, "extend NUMBER_WORDS for the new core-rule count")
        self.assertIn(f"{word} core rules", HOME)


def iron_law() -> str:
    """The Consult core's principle, which the site calls its Iron Law."""
    return CORE.principle


class WhyPageFactsTest(unittest.TestCase):
    """The essay at why/ quotes the Iron Law as core.md states it."""

    def test_iron_law_quote(self) -> None:
        quote = re.search(r"Iron Law: <q>([^<]+)</q>", WHY)
        assert quote is not None, "the essay should quote the Iron Law in a <q>"
        self.assertEqual(quote[1].casefold(), iron_law().casefold())


def row(attribute: str, value: str) -> str:
    """The evidence page's table row whose data attribute names this stage or rule."""
    found = re.search(rf'<tr {attribute}="{re.escape(value)}">(.*?)</tr>', EVIDENCE, re.DOTALL)
    assert found is not None, f"no row with {attribute}={value!r}"
    return found[1]


def cells(row_html: str) -> list[str]:
    return re.findall(r'<td class="num">([^<]+)</td>', row_html)


class EvidencePageFactsTest(unittest.TestCase):
    """Every figure on the evidence page matches the results file it cites."""

    def test_simplicity_table_and_chart_points(self) -> None:
        stages = RESULTS["simplicity_by_stage"]
        for i, (bare, consult) in enumerate(zip(stages["bare"], stages["consult"]), start=1):
            self.assertEqual(cells(row("data-stage", str(i))), [f"{bare:.2f}", f"{consult:.2f}"], f"stage {i}")
            hit = f'data-stage="{i}" data-bare="{bare:.2f}" data-consult="{consult:.2f}"'
            self.assertIn(hit, EVIDENCE, f"chart point for stage {i}")

    def test_home_page_chart_matches_the_evidence_page(self) -> None:
        stages = RESULTS["simplicity_by_stage"]
        for i, (bare, consult) in enumerate(zip(stages["bare"], stages["consult"]), start=1):
            hit = f'data-stage="{i}" data-bare="{bare:.2f}" data-consult="{consult:.2f}"'
            self.assertIn(hit, HOME, f"home chart point for stage {i}")
        self.assertIn(f"fell from {stages['bare'][0]:.2f} to {stages['bare'][-1]:.2f}", HOME)
        self.assertIn(f"between {min(stages['consult']):.2f} and {max(stages['consult']):.2f}", HOME)

    def test_defaults_table(self) -> None:
        for default in RESULTS["defaults"]:
            expected = [f"{default['bare']:.2f}", f"{default['consult']:.2f}"]
            self.assertEqual(cells(row("data-rule", default["id"])), expected, default["id"])

    def test_core_and_working_with_you_table(self) -> None:
        for rule in RESULTS["rules"]:
            expected = [f"{rule['bare']:.2f}", f"{rule['consult']:.2f}"]
            self.assertEqual(cells(row("data-rule", rule["id"])), expected, rule["id"])
            staged_only = rule["n_bare"] == rule["n_consult"] == RESULTS["attempts_per_arm"]
            self.assertEqual("Staged project." in row("data-rule", rule["id"]), staged_only, rule["id"])

    def test_scored_and_unscored_rule_counts(self) -> None:
        scored = len(RESULTS["defaults"]) + len(RESULTS["rules"])
        self.assertIn(f"Of the core’s {RESULTS['core_rules']} rules, this page scores {scored}.", EVIDENCE)
        for rule in RESULTS["untested"]:
            self.assertIn(rule["label"], EVIDENCE, rule["id"])

    def test_every_shortfall_is_listed(self) -> None:
        """A score where Consult beats bare by less than 0.05 must appear in the shortfall table."""
        control = {"id": "default.follow", **RESULTS["follows_the_project"]}
        scores = [*RESULTS["defaults"], *RESULTS["rules"], control]
        shortfalls = {s["id"]: s for s in scores if s["consult"] - s["bare"] < 0.05}
        listed = set(re.findall(r'<tr data-short="([^"]+)">', EVIDENCE))
        self.assertEqual(listed, set(shortfalls))
        for rule_id, score in shortfalls.items():
            expected = [f"{score['bare']:.2f}", f"{score['consult']:.2f}"]
            self.assertEqual(cells(row("data-short", rule_id)), expected, rule_id)

    def test_cost_and_control_figures(self) -> None:
        cost = RESULTS["cost_ratio"]
        self.assertIn(f"{cost['output_tokens']:.1f} times the output tokens", EVIDENCE)
        self.assertIn(f"{cost['agent_seconds']:.1f} times the agent time", EVIDENCE)
        control = RESULTS["follows_the_project"]
        self.assertIn(f"({control['consult']:.2f}, against bare’s {control['bare']:.2f})", EVIDENCE)


class ShippedFilesTest(unittest.TestCase):
    """site/ contains only the pages that are meant to be published."""

    def test_only_shipped_pages(self) -> None:
        pages = {p.relative_to(SITE).as_posix() for p in SITE.rglob("*.html")}
        self.assertEqual(pages, SHIPPED_PAGES)


if __name__ == "__main__":
    unittest.main()
