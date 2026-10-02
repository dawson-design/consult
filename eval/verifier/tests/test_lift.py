"""The lift report: floor rates, noise intervals, judge alignment, the baseline comparison, and the stub arm.

  python3 -m unittest discover eval/verifier/tests
"""

from __future__ import annotations

import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

EVAL_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(EVAL_DIR / "scripts"))

import lift  # noqa: E402


def write_trial(job: Path, task: str, n: int, rewards: dict | None) -> None:
    trial = job / f"{task}__{n}"
    trial.mkdir(parents=True)
    (trial / "result.json").write_text(json.dumps(trial_result(task, rewards)))


def trial_result(task: str, rewards: dict | None) -> dict:
    """rewards None is a trial the agent never finished: an exception and no verifier result."""
    if rewards is None:
        return {"task_name": f"consult/{task}", "verifier_result": None,
                "exception_info": {"exception_type": "AgentTimeoutError"}}
    return {"task_name": f"consult/{task}", "verifier_result": {"rewards": rewards}}


def code_rewards(reward: float, verification: float = 1.0, judge: float | None = 0.5) -> dict:
    rewards = {"reward": reward, "verification": verification, "proof": 1.0, "change_quality": 1.0}
    return rewards if judge is None else {**rewards, "judge": judge}


def arm_rewards(*values: float, judge: float | None = 0.5) -> list[dict]:
    return [code_rewards(v, judge=judge) for v in values]


def stub_sections(report: str) -> list[str]:
    """The skill-content section and the listing-and-hook section of a lift report."""
    return report.split("## Skill content: consult vs stub")[1].split("## Listing and hook: stub vs bare")


class LiftTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def job(self, name: str, trials: dict[str, list[dict]]) -> Path:
        job = self.root / name
        for task, rewards in trials.items():
            for n, r in enumerate(rewards):
                write_trial(job, task, n, r)
        return job

    def summary(self, bare: Path, consult: Path) -> dict:
        return lift.summarize(lift.load_trials(bare), lift.load_trials(consult))

    def test_floor_rate_counts_failed_verification_and_low_reward(self):
        bare = self.job("bare", {"proof-first-bugfix": [code_rewards(0.8, verification=0.0), code_rewards(0.3), code_rewards(0.9)]})
        consult = self.job("consult", {"proof-first-bugfix": [code_rewards(0.9)] * 3})
        row = self.summary(bare, consult)["tasks"][0]
        self.assertAlmostEqual(row["floor_rate"]["bare"], 2 / 3)
        self.assertEqual(row["floor_rate"]["consult"], 0.0)

    def test_a_clear_lift_has_an_interval_that_excludes_zero(self):
        bare = self.job("bare", {"proof-first-bugfix": [code_rewards(0.3), code_rewards(0.35), code_rewards(0.4)]})
        consult = self.job("consult", {"proof-first-bugfix": [code_rewards(0.8), code_rewards(0.85), code_rewards(0.9)]})
        lo, hi = self.summary(bare, consult)["suite"]["reward_interval"]
        self.assertGreater(lo, 0.0)
        self.assertEqual(lift.noise_verdict(lo, hi), "interval excludes 0")

    def test_overlapping_arms_are_reported_as_noise(self):
        bare = self.job("bare", {"proof-first-bugfix": [code_rewards(0.3), code_rewards(0.9), code_rewards(0.6)]})
        consult = self.job("consult", {"proof-first-bugfix": [code_rewards(0.9), code_rewards(0.3), code_rewards(0.7)]})
        lo, hi = self.summary(bare, consult)["suite"]["reward_interval"]
        self.assertEqual(lift.noise_verdict(lo, hi), "not distinguishable from noise")

    def test_one_trial_per_task_gives_no_interval(self):
        bare = self.job("bare", {"proof-first-bugfix": [code_rewards(0.3)]})
        consult = self.job("consult", {"proof-first-bugfix": [code_rewards(0.9)]})
        suite = self.summary(bare, consult)["suite"]
        self.assertIsNone(suite["reward_interval"])
        self.assertIn("no interval", lift.render_comparison(suite, "Suite lift")[0])

    def test_a_task_missing_from_the_earlier_job_is_listed_not_scored_as_zero(self):
        earlier = lift.load_trials(self.job("earlier", {"proof-first-bugfix": [code_rewards(0.5)] * 2}))
        consult = lift.load_trials(self.job("consult", {"proof-first-bugfix": [code_rewards(0.5)] * 2,
                                                        "api-error-contract": [code_rewards(0.9)] * 2}))
        result = lift.compare(earlier, consult)
        self.assertEqual(result["missing"], ["consult/api-error-contract"])
        self.assertAlmostEqual(result["reward"], 0.0)

    def test_bare_tasks_the_consult_job_did_not_run_are_left_out(self):
        bare = self.job("bare", {"proof-first-bugfix": [code_rewards(0.5)], "api-error-contract": [code_rewards(0.9)]})
        consult = self.job("consult", {"proof-first-bugfix": [code_rewards(0.7)]})
        summary = self.summary(bare, consult)
        self.assertEqual([r["task"] for r in summary["tasks"]], ["consult/proof-first-bugfix"])
        self.assertAlmostEqual(summary["suite_lift"], 0.2)

    def test_a_judge_free_job_is_compared_on_deterministic_dimensions(self):
        bare = self.job("bare", {"proof-first-bugfix": [code_rewards(0.55, judge=0.0)]})
        consult = self.job("consult", {"proof-first-bugfix": [code_rewards(1.0, judge=None)]})
        summary = self.summary(bare, consult)
        self.assertTrue(summary["judge_excluded"])
        self.assertAlmostEqual(summary["suite_lift"], 0.0)

    def test_the_report_compares_against_an_earlier_consult_job(self):
        bare = self.job("bare", {"proof-first-bugfix": [code_rewards(0.4)] * 3})
        earlier = self.job("earlier", {"proof-first-bugfix": [code_rewards(0.9)] * 3})
        consult = self.job("consult", {"proof-first-bugfix": [code_rewards(0.4)] * 3})
        with redirect_stdout(io.StringIO()):
            lift.main(["lift.py", str(bare), str(consult), "--baseline-consult", str(earlier)])
        report = (self.root / "lift" / "consult.md").read_text()
        self.assertIn("## Against the earlier Consult job earlier", report)
        self.assertIn("Reward change: -0.500", report)

    def one_task_job(self, name: str, rewards: list[dict | None]) -> Path:
        return self.job(name, {"proof-first-bugfix": rewards})

    def stub_report(self, bare: list[dict], stub: list[dict | None], consult: list[dict]) -> tuple[str, dict]:
        jobs = {name: self.one_task_job(name, rewards)
                for name, rewards in (("bare", bare), ("stub", stub), ("consult", consult))}
        with redirect_stdout(io.StringIO()):
            lift.main(["lift.py", str(jobs["bare"]), str(jobs["consult"]), "--stub", str(jobs["stub"])])
        return (self.root / "lift" / "consult.md").read_text(), json.loads((self.root / "lift" / "consult.json").read_text())

    def test_the_stub_job_splits_lift_into_skill_content_and_listing_with_hook(self):
        report, summary = self.stub_report(arm_rewards(0.3, 0.35, 0.4), arm_rewards(0.5, 0.55, 0.6), arm_rewards(0.8, 0.85, 0.9))
        content, listing = report.split("## Skill content: consult vs stub")[1].split("## Listing and hook: stub vs bare")
        self.assertIn("| consult/proof-first-bugfix | 0.550 | 0.850 | +0.300 |", content)
        self.assertIn("Reward change: +0.300 (90% interval", content)
        self.assertIn("Floor rate change: +0%", content)
        self.assertIn("Verdict: consult beats stub, interval excludes 0.", content)
        self.assertIn("| consult/proof-first-bugfix | 0.350 | 0.550 | +0.200 |", listing)
        self.assertIn("Reward change: +0.200 (90% interval", listing)
        self.assertIn("Floor rate change: -100%", listing)
        self.assertGreater(summary["stub"]["content"]["reward_interval"][0], 0.0)

    def test_a_stub_that_matches_consult_is_reported_as_noise(self):
        report, _ = self.stub_report(arm_rewards(0.3, 0.35, 0.4), arm_rewards(0.3, 0.9, 0.6), arm_rewards(0.9, 0.3, 0.7))
        self.assertIn("Verdict: consult does not beat stub beyond noise, interval contains 0.", report)

    def test_a_stub_that_beats_consult_is_reported_as_lowering_the_reward(self):
        report, _ = self.stub_report(arm_rewards(0.3, 0.35, 0.4), arm_rewards(0.8, 0.85, 0.9), arm_rewards(0.3, 0.35, 0.4))
        self.assertIn("Verdict: consult scores below stub, interval excludes 0. Skill content lowers the reward.", report)

    def test_a_stub_job_with_one_trial_per_task_gives_no_verdict(self):
        report, _ = self.stub_report(arm_rewards(0.3, 0.35, 0.4), arm_rewards(0.5), arm_rewards(0.8, 0.85, 0.9))
        self.assertIn("Verdict: no interval, so this run cannot say whether skill content changes the reward.", report)

    def test_a_judge_free_stub_job_is_compared_on_deterministic_dimensions(self):
        report, _ = self.stub_report(arm_rewards(0.3, 0.35, 0.4), arm_rewards(0.5, 0.55, 0.6, judge=None),
                                     arm_rewards(0.8, 0.85, 0.9))
        content, listing = stub_sections(report)
        self.assertIn(f"| consult/proof-first-bugfix | 1.000 | 1.000 | +0.000 |\n\nReward change", content)
        self.assertIn(lift.JUDGE_EXCLUDED_NOTE, content)
        self.assertIn(lift.JUDGE_EXCLUDED_NOTE, listing)

    def test_stub_trials_without_a_reward_are_listed_in_both_stub_sections(self):
        stub = [*arm_rewards(0.82), None, None]
        report, _ = self.stub_report(arm_rewards(0.8, 0.82, 0.84), stub, arm_rewards(0.8, 0.82, 0.84))
        for section in stub_sections(report):
            self.assertIn("Failed trials (no reward counts as 0): proof-first-bugfix__1, proof-first-bugfix__2", section)

    def test_trials_without_a_reward_withhold_the_skill_content_verdict(self):
        stub = [*arm_rewards(0.82), None, None]
        report, _ = self.stub_report(arm_rewards(0.8, 0.82, 0.84), stub, arm_rewards(0.8, 0.82, 0.84))
        self.assertIn("Verdict: withheld, failed trials are listed above. "
                      "Rerun them before reading the change as a skill-content effect.", report)
        self.assertNotIn("Skill content raises the reward", report)


if __name__ == "__main__":
    unittest.main()
