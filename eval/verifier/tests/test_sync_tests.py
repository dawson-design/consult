"""The vendored verifier copies: which reward weights each task's tests/reward.toml gets.

  python3 -m unittest discover eval/verifier/tests
"""

from __future__ import annotations

import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

EVAL_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(EVAL_DIR / "scripts"))

import sync_tests  # noqa: E402

WEIGHTS_LINE = ("weights = {{ verification = 0.275, proof = 0.1925, change_quality = 0.0825, judge = 0.45, "
                "skill_triggering = 0.0, non_interruption = 0.0, rules = {rules} }}")


class RewardWeightTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.shared = Path(self._tmp.name) / "shared"
        shutil.copytree(sync_tests.SHARED_DIR, self.shared)
        toml = self.shared / "reward.code.toml"
        text = toml.read_text()
        start = text.index("weights = {")
        toml.write_text(text[:start] + WEIGHTS_LINE.format(rules=0.2) + "\n")

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def planned_reward_toml(self, task: str) -> str:
        with mock.patch.object(sync_tests, "SHARED_DIR", self.shared):
            pairs = sync_tests.planned_copies(sync_tests.TASKS_DIR / task)
        source = next(src for src, dest in pairs if dest.parts[-2:] == ("tests", "reward.toml"))
        return sync_tests.source_bytes(source).decode()

    def test_a_task_that_scores_rules_keeps_the_shared_rules_weight(self):
        self.assertIn(WEIGHTS_LINE.format(rules=0.2), self.planned_reward_toml("money-field-change"))

    def test_a_task_that_lists_no_rules_gets_a_zero_rules_weight(self):
        """Its rules dimension is a placeholder that scores 1.0, so any weight would be a free point."""
        self.assertIn(WEIGHTS_LINE.format(rules=0.0), self.planned_reward_toml("proof-first-bugfix"))

    def test_sign_off_rules_alone_do_not_count_as_scored_rules(self):
        """Sign-off rules score in the brief step's suite, not in the root rules dimension."""
        self.assertEqual(sync_tests.scored_rule_ids(["scaffolding.1", "domain-modeling.10"]), [])
        self.assertEqual(sync_tests.scored_rule_ids(["scaffolding.1", "api.1"]), ["api.1"])

    def test_a_shared_file_without_a_rules_weight_stops_the_sync(self):
        """RewardKit would weigh the placeholder at 1.0, the free point the zeroing prevents."""
        toml = self.shared / "reward.code.toml"
        toml.write_text(toml.read_text().replace(", rules = 0.2", ""))
        with self.assertRaisesRegex(SystemExit, "must name the rules weight once"):
            self.planned_reward_toml("proof-first-bugfix")


if __name__ == "__main__":
    unittest.main()
