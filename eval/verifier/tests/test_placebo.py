"""Placebo core: the core's shape and length with rules no check scores, printed by the same hook.

python3 -m unittest discover eval/verifier/tests
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

EVAL_DIR = Path(__file__).resolve().parents[2]
REPO_DIR = EVAL_DIR.parent
sys.path.insert(0, str(EVAL_DIR / "scripts"))
sys.path.insert(0, str(REPO_DIR / "scripts"))

import placebo
import validate_skills

CORE = REPO_DIR / "agents" / ".agents" / "core.md"
PLUGIN_HOOKS = REPO_DIR / "plugin" / "hooks" / "hooks.json"
RUBRICS_DIR = EVAL_DIR / "verifier" / "rubrics"
TITLE = "# Consult core"


def outline(text: str) -> list[tuple[str, list[int], int]]:
    """Per heading from the title down: its level, its numbered rules, and its nested bullets."""
    sections: list[tuple[str, list[int], int]] = []
    for line in text[text.index(TITLE) :].splitlines():
        if line.startswith("#"):
            sections.append((line.split()[0], [], 0))
        elif rule := re.match(r"(\d+)\. ", line):
            sections[-1][1].append(int(rule.group(1)))
        elif re.match(r"\s+- ", line):
            level, rules, bullets = sections[-1]
            sections[-1] = (level, rules, bullets + 1)
    return sections


def key_phrases() -> list[str]:
    """Every rubric item's key_phrase, the rule text the judges score against."""
    return [
        item["key_phrase"]
        for path in sorted(RUBRICS_DIR.glob("*.json"))
        for item in json.loads(path.read_text())["items"]
        if "key_phrase" in item
    ]


class PlaceboCoreTests(unittest.TestCase):
    core = CORE.read_text(encoding="utf8")
    placebo = placebo.CORE.read_text(encoding="utf8")

    def test_the_opening_paragraph_matches_the_core_byte_for_byte(self):
        self.assertEqual(self.placebo[: self.placebo.index(TITLE)], self.core[: self.core.index(TITLE)])

    def test_each_section_has_the_cores_heading_level_rule_numbers_and_nested_bullets(self):
        self.assertEqual(outline(self.placebo), outline(self.core))

    def test_the_word_count_is_within_five_percent_of_the_core(self):
        core, placebo_words = validate_skills.word_count(self.core), validate_skills.word_count(self.placebo)
        self.assertLessEqual(abs(placebo_words - core), 0.05 * core)

    def test_the_rules_are_written_calmly(self):
        self.assertEqual(validate_skills.EMPHATIC.findall(self.placebo), [])

    def test_no_rubric_key_phrase_appears_in_the_placebo(self):
        text = self.placebo.lower()
        self.assertEqual([p for p in key_phrases() if p.lower() in text], [])


class PlaceboBuildTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.built = placebo.build(self.root / "placebo-hooks")

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def command(self, hooks: dict) -> str:
        return hooks["hooks"]["SessionStart"][0]["hooks"][0]["command"]

    def test_the_hook_prints_the_placebo_core(self):
        printed = subprocess.run(
            ["bash", "-c", self.command(json.loads(self.built.read_text()))], capture_output=True, text=True, check=True
        )
        self.assertEqual(printed.stdout, placebo.CORE.read_text(encoding="utf8").strip() + "\n")

    def test_the_settings_differ_from_the_plugin_hook_only_in_the_command(self):
        built, plugin = json.loads(self.built.read_text()), json.loads(PLUGIN_HOOKS.read_text())
        self.assertNotEqual(self.command(built), self.command(plugin))
        built["hooks"]["SessionStart"][0]["hooks"][0]["command"] = self.command(plugin)
        self.assertEqual(built, plugin)

    def test_a_second_build_reuses_the_same_file(self):
        self.assertEqual(placebo.build(self.root / "placebo-hooks"), self.built)
        self.assertEqual([p.name for p in (self.root / "placebo-hooks").iterdir()], [self.built.parent.name])


if __name__ == "__main__":
    unittest.main()
