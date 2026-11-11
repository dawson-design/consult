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
from unittest import mock

EVAL_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(EVAL_DIR / "scripts"))

import lift


def write_trial(job: Path, task: str, n: int, rewards: dict | None) -> None:
    trial = job / f"{task}__{n}"
    trial.mkdir(parents=True)
    (trial / "result.json").write_text(json.dumps(trial_result(task, rewards)))


def trial_result(task: str, rewards: dict | None) -> dict:
    """rewards None is a trial the agent never finished: an exception and no verifier result."""
    if rewards is None:
        return {
            "task_name": f"consult/{task}",
            "verifier_result": None,
            "exception_info": {"exception_type": "AgentTimeoutError"},
        }
    return {"task_name": f"consult/{task}", "verifier_result": {"rewards": rewards}}


def code_rewards(reward: float, verification: float = 1.0, judge: float | None = 0.5) -> dict:
    rewards = {"reward": reward, "verification": verification, "proof": 1.0, "change_quality": 1.0}
    return rewards if judge is None else {**rewards, "judge": judge}


def rubric(reward: float, score: float) -> dict:
    """Code rewards scored by the rubric judges instead of the generic judge."""
    return {**code_rewards(reward, judge=None), "rubric": score}


def arm_rewards(*values: float, judge: float | None = 0.5) -> list[dict]:
    return [code_rewards(v, judge=judge) for v in values]


BUNDLE = """# Changes against the starting repository

## Diff

```diff
diff --git a/app.js b/app.js
--- a/app.js
+++ b/app.js
@@ -1,2 +1,3 @@
 const a = 1;
-const b = 2;
+const b = 3;
+const c = 4;
```

## New file: app.test.js

```
test("a", () => {
  expect(a).toBe(1);
});
```

## Final agent message

Done.
"""


def agent_run(output_tokens: int, cost: float, seconds: int) -> tuple[dict, dict]:
    """A Harbor AgentContext and the agent_execution timing that spans seconds."""
    context = {"n_input_tokens": 50_000, "n_cache_tokens": 40_000, "n_output_tokens": output_tokens, "cost_usd": cost}
    timing = {
        "started_at": "2026-10-09T13:00:00Z",
        "finished_at": f"2026-10-09T13:{seconds // 60:02d}:{seconds % 60:02d}Z",
    }
    return context, timing


def trajectory(*messages: str) -> dict:
    """An ATIF trajectory: the user prompt, then one agent step per message."""
    steps = [{"source": "user", "message": "Fix the bug."}]
    return {"steps": steps + [{"source": "agent", "message": m} for m in messages]}


def write_costed_trial(job: Path, task: str, n: int, output_tokens: int, cost: float = 1.0, seconds: int = 60) -> Path:
    """A single-step trial with Harbor's agent records, a trajectory, and a judge bundle."""
    trial = job / f"{task}__{n}"
    (trial / "agent").mkdir(parents=True)
    (trial / "verifier").mkdir()
    context, timing = agent_run(output_tokens, cost, seconds)
    result = {**trial_result(task, code_rewards(0.8)), "agent_result": context, "agent_execution": timing}
    (trial / "result.json").write_text(json.dumps(result))
    (trial / "agent" / "trajectory.json").write_text(
        json.dumps(trajectory("Reading the code.", "Which file?", "Fixed it."))
    )
    (trial / "verifier" / "judge-bundle.md").write_text(BUNDLE)
    return trial


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
        bare = self.job(
            "bare", {"proof-first-bugfix": [code_rewards(0.8, verification=0.0), code_rewards(0.3), code_rewards(0.9)]}
        )
        consult = self.job("consult", {"proof-first-bugfix": [code_rewards(0.9)] * 3})
        row = self.summary(bare, consult)["tasks"][0]
        self.assertAlmostEqual(row["floor_rate"]["bare"], 2 / 3)
        self.assertEqual(row["floor_rate"]["consult"], 0.0)

    def test_a_clear_lift_has_an_interval_that_excludes_zero(self):
        bare = self.job("bare", {"proof-first-bugfix": [code_rewards(0.3), code_rewards(0.35), code_rewards(0.4)]})
        consult = self.job(
            "consult", {"proof-first-bugfix": [code_rewards(0.8), code_rewards(0.85), code_rewards(0.9)]}
        )
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
        consult = lift.load_trials(
            self.job(
                "consult",
                {"proof-first-bugfix": [code_rewards(0.5)] * 2, "api-error-contract": [code_rewards(0.9)] * 2},
            )
        )
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

    def test_a_trial_whose_rubric_judges_failed_strips_model_scores_from_that_task_only(self):
        bare = self.job(
            "bare",
            {"proof-first-bugfix": [rubric(0.5, 0.2), rubric(0.5, 0.2)], "api-error-contract": [rubric(0.5, 0.2)]},
        )
        consult = self.job(
            "consult",
            {
                "proof-first-bugfix": [rubric(0.9, 0.9), code_rewards(0.9, judge=None)],
                "api-error-contract": [rubric(0.9, 0.9)],
            },
        )
        summary = self.summary(bare, consult)
        self.assertTrue(summary["judge_excluded"])
        rows = {r["task"]: r for r in summary["tasks"]}
        self.assertNotIn("rubric", rows["consult/proof-first-bugfix"]["dimensions"])
        self.assertIn("rubric", rows["consult/api-error-contract"]["dimensions"])

    def test_judge_free_rescoring_uses_the_tasks_own_reward_weights(self):
        """A task's vendored reward.toml can differ from the shared one: sync_tests zeroes rules where none score."""
        tests = self.root / "tasks" / "proof-first-bugfix" / "tests"
        tests.mkdir(parents=True)
        (tests / "consult.json").write_text(json.dumps({"kind": "code"}))
        (tests / "reward.toml").write_text(
            "[[reward]]\nweights = { verification = 0.5, proof = 0.5, "
            "change_quality = 0.0, judge = 0.5, rules = 0.0 }\n"
        )
        bare = self.job("bare", {"proof-first-bugfix": [code_rewards(0.4, judge=0.0)]})
        consult = self.job(
            "consult", {"proof-first-bugfix": [{**code_rewards(0.9, judge=None), "proof": 0.0, "rules": 1.0}]}
        )
        with mock.patch.object(lift, "TASKS_DIR", self.root / "tasks"):
            row = self.summary(bare, consult)["tasks"][0]
        self.assertAlmostEqual(row["consult"], 0.5)

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
        jobs = {
            name: self.one_task_job(name, rewards)
            for name, rewards in (("bare", bare), ("stub", stub), ("consult", consult))
        }
        with redirect_stdout(io.StringIO()):
            lift.main(["lift.py", str(jobs["bare"]), str(jobs["consult"]), "--stub", str(jobs["stub"])])
        return (self.root / "lift" / "consult.md").read_text(), json.loads(
            (self.root / "lift" / "consult.json").read_text()
        )

    def test_the_stub_job_splits_lift_into_skill_content_and_listing_with_hook(self):
        report, summary = self.stub_report(
            arm_rewards(0.3, 0.35, 0.4), arm_rewards(0.5, 0.55, 0.6), arm_rewards(0.8, 0.85, 0.9)
        )
        content, listing = report.split("## Skill content: consult vs stub")[1].split(
            "## Listing and hook: stub vs bare"
        )
        self.assertIn("| consult/proof-first-bugfix | 0.550 | 0.850 | +0.300 |", content)
        self.assertIn("Reward change: +0.300 (90% interval", content)
        self.assertIn("Floor rate change: +0%", content)
        self.assertIn("Verdict: consult beats stub, interval excludes 0.", content)
        self.assertIn("| consult/proof-first-bugfix | 0.350 | 0.550 | +0.200 |", listing)
        self.assertIn("Reward change: +0.200 (90% interval", listing)
        self.assertIn("Floor rate change: -100%", listing)
        self.assertGreater(summary["stub"]["content"]["reward_interval"][0], 0.0)

    def test_a_stub_that_matches_consult_is_reported_as_noise(self):
        report, _ = self.stub_report(
            arm_rewards(0.3, 0.35, 0.4), arm_rewards(0.3, 0.9, 0.6), arm_rewards(0.9, 0.3, 0.7)
        )
        self.assertIn("Verdict: consult does not beat stub beyond noise, interval contains 0.", report)

    def test_a_stub_that_beats_consult_is_reported_as_lowering_the_reward(self):
        report, _ = self.stub_report(
            arm_rewards(0.3, 0.35, 0.4), arm_rewards(0.8, 0.85, 0.9), arm_rewards(0.3, 0.35, 0.4)
        )
        self.assertIn(
            "Verdict: consult scores below stub, interval excludes 0. Skill content lowers the reward.", report
        )

    def test_a_stub_job_with_one_trial_per_task_gives_no_verdict(self):
        report, _ = self.stub_report(arm_rewards(0.3, 0.35, 0.4), arm_rewards(0.5), arm_rewards(0.8, 0.85, 0.9))
        self.assertIn("Verdict: no interval, so this run cannot say whether skill content changes the reward.", report)

    def test_a_judge_free_stub_job_is_compared_on_deterministic_dimensions(self):
        report, _ = self.stub_report(
            arm_rewards(0.3, 0.35, 0.4), arm_rewards(0.5, 0.55, 0.6, judge=None), arm_rewards(0.8, 0.85, 0.9)
        )
        content, listing = stub_sections(report)
        self.assertIn("| consult/proof-first-bugfix | 1.000 | 1.000 | +0.000 |\n\nReward change", content)
        self.assertIn(lift.JUDGE_EXCLUDED_NOTE, content)
        self.assertIn(lift.JUDGE_EXCLUDED_NOTE, listing)

    def test_stub_trials_without_a_reward_are_listed_in_both_stub_sections(self):
        stub = [*arm_rewards(0.82), None, None]
        report, _ = self.stub_report(arm_rewards(0.8, 0.82, 0.84), stub, arm_rewards(0.8, 0.82, 0.84))
        for section in stub_sections(report):
            self.assertIn(
                "Failed trials (no reward counts as 0): proof-first-bugfix__1, proof-first-bugfix__2", section
            )

    def test_trials_without_a_reward_withhold_the_skill_content_verdict(self):
        stub = [*arm_rewards(0.82), None, None]
        report, _ = self.stub_report(arm_rewards(0.8, 0.82, 0.84), stub, arm_rewards(0.8, 0.82, 0.84))
        self.assertIn(
            "Verdict: withheld, failed trials are listed above. "
            "Rerun them before reading the change as a skill-content effect.",
            report,
        )
        self.assertNotIn("Skill content raises the reward", report)

    def cost_of(self, trial: Path) -> dict:
        entries = lift.load_trials(trial.parent)
        return next(iter(entries.values()))[0]["cost"]

    def test_a_trial_reports_tokens_cost_agent_time_turns_changed_lines_and_questions(self):
        trial = write_costed_trial(
            self.root / "consult", "proof-first-bugfix", 0, output_tokens=1200, cost=0.5, seconds=90
        )
        self.assertEqual(
            self.cost_of(trial),
            {
                "output_tokens": 1200,
                "cost_usd": 0.5,
                "agent_seconds": 90.0,
                "turns": 3,
                "lines_changed": 6,
                "questions": 1,
            },
        )

    def multi_step_trial(self, resumed: bool, brief: tuple[dict, dict], build: tuple[dict, dict]) -> Path:
        """A brief-then-build trial whose final step holds the trajectory and bundle."""
        trial = write_costed_trial(self.root / "consult", "money-field-change", 0, output_tokens=0)
        result = json.loads((trial / "result.json").read_text())
        result.pop("agent_result"), result.pop("agent_execution")
        result["config"] = {"agent": {"resume_trajectory": resumed}}
        result["step_results"] = [
            {"step_name": "brief", "agent_result": brief[0], "agent_execution": brief[1]},
            {"step_name": "build", "agent_result": build[0], "agent_execution": build[1]},
        ]
        (trial / "result.json").write_text(json.dumps(result))
        (trial / "steps" / "build").mkdir(parents=True)
        (trial / "agent").rename(trial / "steps" / "build" / "agent")
        (trial / "verifier").rename(trial / "steps" / "build" / "verifier")
        return trial

    def test_a_resumed_multi_step_trial_takes_tokens_from_its_final_step(self):
        """With resume_trajectory the build step continues the brief's session, so its record already holds the brief."""
        trial = self.multi_step_trial(True, agent_run(300, 0.25, 30), agent_run(1200, 1.0, 120))
        cost = self.cost_of(trial)
        self.assertEqual((cost["output_tokens"], cost["agent_seconds"]), (1200, 150.0))
        self.assertIsNone(cost["cost_usd"])
        self.assertEqual((cost["turns"], cost["lines_changed"]), (3, 6))

    def test_a_multi_step_trial_without_resume_sums_its_steps(self):
        trial = self.multi_step_trial(False, agent_run(300, 0.25, 30), agent_run(900, 0.75, 120))
        cost = self.cost_of(trial)
        self.assertEqual((cost["output_tokens"], cost["cost_usd"], cost["agent_seconds"]), (1200, 1.0, 150.0))

    def test_only_lines_inside_hunks_count_as_changed(self):
        trial = write_costed_trial(self.root / "consult", "proof-first-bugfix", 0, output_tokens=1)
        hunk_with_dashes = BUNDLE.replace("-const b = 2;", "--- a/looks-like-a-header")
        second_file = (
            "+const c = 4;\ndiff --git a/old.js b/old.js\ndeleted file mode 100644\n--- a/old.js\n"
            "+++ /dev/null\n@@ -1 +0,0 @@\n-gone();"
        )
        (trial / "verifier" / "judge-bundle.md").write_text(hunk_with_dashes.replace("+const c = 4;", second_file))
        self.assertEqual(self.cost_of(trial)["lines_changed"], 7)

    def test_a_trial_without_agent_records_or_bundle_reports_none_not_zero(self):
        write_trial(self.root / "consult", "proof-first-bugfix", 0, code_rewards(0.8))
        cost = self.cost_of(self.root / "consult" / "proof-first-bugfix__0")
        self.assertEqual(cost, dict.fromkeys(lift.COST_METRICS))

    def costed_job(self, name: str, tokens: list[int]) -> Path:
        for n, t in enumerate(tokens):
            write_costed_trial(self.root / name, "proof-first-bugfix", n, output_tokens=t)
        return self.root / name

    def test_the_report_gives_each_cost_metric_per_arm_with_its_change_and_interval(self):
        bare, consult = self.costed_job("bare", [1000, 1100, 1200]), self.costed_job("consult", [1500, 1600, 1700])
        with redirect_stdout(io.StringIO()):
            lift.main(["lift.py", str(bare), str(consult)])
        summary = json.loads((self.root / "lift" / "consult.json").read_text())
        tokens = summary["cost"]["output_tokens"]
        self.assertEqual((tokens["bare"], tokens["consult"], tokens["change"]), (1100.0, 1600.0, 500.0))
        self.assertGreater(tokens["interval"][0], 0.0)
        self.assertIsNone(summary["cost"]["turns"]["interval"])
        report = (self.root / "lift" / "consult.md").read_text()
        self.assertIn("| output tokens | 1 | 1,100 | 1,600 | +500 (+45%) | +", report)

    def test_a_metric_with_one_recorded_trial_per_arm_gets_no_interval(self):
        bare = self.costed_job("bare", [1000])
        write_trial(bare, "proof-first-bugfix", 1, code_rewards(0.8))
        consult = self.costed_job("consult", [1500, 1500])
        tokens = lift.summarize(lift.load_trials(bare), lift.load_trials(consult))["cost"]["output_tokens"]
        self.assertEqual(tokens["change"], 500.0)
        self.assertIsNone(tokens["interval"])

    def test_trials_missing_a_metric_are_left_out_of_its_mean(self):
        bare = self.costed_job("bare", [1000, 1200])
        write_trial(bare, "proof-first-bugfix", 2, code_rewards(0.8))
        consult = self.costed_job("consult", [1500, 1700, 1600])
        summary = lift.summarize(lift.load_trials(bare), lift.load_trials(consult))
        self.assertEqual(summary["cost"]["output_tokens"]["bare"], 1100.0)


class RuleScorecardTests(unittest.TestCase):
    def test_a_rule_a_trial_could_not_act_on_leaves_its_count_and_mean(self):
        # core.7 had no commit in one consult trial: that trial is left out, not scored 0 or 1.
        bare = {"t": [{"rules": {"core.7": 0.0}}, {"rules": {"core.7": 1.0}}]}
        consult = {"t": [{"rules": {"core.7": 1.0}}, {"rules": {}}]}

        row = lift.rule_scorecard(bare, consult)[0]

        self.assertEqual((row["bare"], row["consult"], row["n_bare"], row["n_consult"]), (0.5, 1.0, 2, 1))

    def test_judge_answers_score_their_rules_in_rows_of_their_own(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "judge-items.json"
            answers = [{"rules": ["core.3"], "answer": a} for a in ("yes", "no", "unknown")]
            path.write_text(json.dumps({"items": answers + [{"rules": ["default.15"], "answer": "yes"}]}))
            rates = lift.judge_rule_rates(path)
        bare = {"t": [{"rules": {"core.3": 0.0}, "judge_rules": {"core.3": 0.0}}]}
        consult = {"t": [{"rules": {"core.3": 1.0}, "judge_rules": rates}]}

        rows = {(r["rule"], r["method"]): r for r in lift.rule_scorecard(bare, consult)}

        self.assertEqual(rates, {"core.3": 0.5, "default.15": 1.0})
        self.assertEqual((rows["core.3", "judge"]["consult"], rows["core.3", "check"]["consult"]), (0.5, 1.0))

    def test_trial_evidence_drops_the_rules_the_verifier_marked_not_applicable(self):
        with tempfile.TemporaryDirectory() as tmp:
            verifier = Path(tmp) / "steps" / "continue" / "verifier"
            verifier.mkdir(parents=True)
            criteria = [{"name": "core.7", "value": 1.0}, {"name": "default.13", "value": 0.5}]
            (verifier / "reward-details.json").write_text(json.dumps({"rules": {"criteria": criteria}}))
            (verifier / "rules-na.json").write_text(json.dumps(["core.7"]))
            result = {"step_results": [{"step_name": "continue"}]}

            evidence = lift.trial_evidence(Path(tmp), result, {})

        self.assertEqual(evidence["rules"], {"default.13": 0.5})


TASK = "consult/staged-commissions"
PARTS = ("function_shape", "logic_purity", "state_isolation", "acyclic_imports", "no_speculative_abstraction")


def stage_record(source: int, test: int, spec: int, part: float | None) -> dict:
    """One stage of house_rules.record_stage_shape: line counts, and every part at `part` (None: nothing built)."""
    parts = None if part is None else dict.fromkeys(PARTS, part)
    return {"lines": {"source": source, "test": test, "spec": spec}, "parts": parts}


class StageTableTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def job(self, name: str, stages: list[dict | None]) -> Path:
        """A staged-commissions job, one trial per entry; None writes no stage-shape.json."""
        job = self.root / name
        for n, record in enumerate(stages):
            write_trial(job, "staged-commissions", n, code_rewards(0.8))
            if record is not None:
                (job / f"staged-commissions__{n}" / "verifier").mkdir()
                (job / f"staged-commissions__{n}" / "verifier" / "stage-shape.json").write_text(json.dumps(record))
        return job

    def report(self, bare: Path, consult: Path) -> tuple[dict, str]:
        summary = lift.summarize(lift.load_trials(bare), lift.load_trials(consult))
        return summary, lift.render_markdown(summary, bare, consult)

    def test_each_arm_reports_mean_lines_and_parts_per_stage(self):
        bare = self.job(
            "bare",
            [
                {"1": stage_record(100, 40, 0, 0.8), "5": stage_record(500, 100, 0, 0.6)},
                {"1": stage_record(120, 60, 0, 1.0), "5": stage_record(700, 140, 0, 0.8)},
            ],
        )
        consult = self.job(
            "consult",
            [
                {"1": stage_record(200, 150, 80, 1.0), "5": stage_record(900, 400, 200, 0.9)},
                {"1": stage_record(220, 170, 100, None), "5": stage_record(1100, 600, 300, 1.0)},
            ],
        )

        summary, report = self.report(bare, consult)
        stage_one = summary["stages"][0]

        self.assertEqual([(r["task"], r["stage"]) for r in summary["stages"]], [(TASK, 1), (TASK, 5)])
        self.assertEqual(stage_one["bare"]["lines"], {"source": 110, "test": 50, "spec": 0})
        self.assertEqual(stage_one["consult"]["lines"], {"source": 210, "test": 160, "spec": 90})
        self.assertAlmostEqual(stage_one["bare"]["parts"]["logic_purity"], 0.9)
        # A trial that built nothing by stage 1 counts toward its lines, not its parts.
        self.assertEqual((stage_one["consult"]["trials"], stage_one["consult"]["parts"]["acyclic_imports"]), (2, 1.0))
        self.assertIn("| consult/staged-commissions | 1 | 110 / 210 | 50 / 160 | 0 / 90 | 2 / 2 |", report)
        self.assertIn("| consult/staged-commissions | 5 | 600 / 1,000 | 120 / 500 | 0 / 250 | 2 / 2 |", report)
        self.assertIn("| consult/staged-commissions | 5 | 0.70 / 0.95 | 0.70 / 0.95 |", report)
        self.assertLess(report.index("## Size per stage"), report.index("## Simplicity parts per stage"))
        self.assertEqual(tuple(lift.STAGE_PARTS), PARTS)

    def test_an_arm_without_stage_records_shows_dashes(self):
        summary, report = self.report(
            self.job("bare", [None]), self.job("consult", [{"5": stage_record(10, 5, 1, 1.0)}])
        )

        self.assertEqual(summary["stages"][0]["bare"]["trials"], 0)
        self.assertIn("| consult/staged-commissions | 5 | - / 10 | - / 5 | - / 1 | 0 / 1 |", report)
        self.assertIn("| consult/staged-commissions | 5 | - / 1.00 |", report)

    def test_jobs_without_stage_records_print_no_stage_tables(self):
        summary, report = self.report(self.job("bare", [None]), self.job("consult", [None]))

        self.assertEqual(summary["stages"], [])
        self.assertNotIn("per stage", report)


if __name__ == "__main__":
    unittest.main()
