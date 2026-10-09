"""Tier arm plans, arm job configs, fast-tier task selection, and baselines.

  python3 -m unittest discover eval/verifier/tests
"""

from __future__ import annotations

import argparse
import io
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

EVAL_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(EVAL_DIR / "scripts"))

import baseline  # noqa: E402
import run  # noqa: E402
import selection  # noqa: E402
import stub  # noqa: E402

AGENT = {"name": "claude-code", "model_name": "anthropic/claude-sonnet-5",
         "kwargs": {"reasoning_effort": "medium", "version": "2.1.282"}}
HOOK = {"hooks": {"SessionStart": [{"hooks": [{"type": "command", "command": "echo Consult is installed."}]}]}}
JOB_ARGS = argparse.Namespace(suite="rules", tier=None, agent="claude-code", effort=None, attempts=1,
                              concurrency=2, install_only=False, drop_references=())


def parse(argv: list[str]) -> argparse.Namespace:
    with mock.patch.object(sys, "argv", ["run.py", *argv]):
        return run.parse_args()


def write_result(trial: Path, rewards: dict | None) -> None:
    trial.mkdir(parents=True)
    (trial / "result.json").write_text(json.dumps({"verifier_result": rewards and {"rewards": rewards}}))


def frontmatter(skills_dir: str, skill: str) -> bytes:
    return stub.FRONTMATTER_RE.match((Path(skills_dir) / skill / "SKILL.md").read_bytes()).group(0)


class TierPlanTests(unittest.TestCase):
    def test_the_release_tier_runs_bare_stub_and_consult(self):
        args = parse(["--tier", "release", "--agent", "claude-code"])
        self.assertEqual(run.plan_arms(args.arms.split(","), None, needs_lift=True), ["bare", "stub", "consult"])

    def test_the_fast_tier_still_runs_the_consult_arm_only(self):
        self.assertEqual(parse(["--tier", "fast"]).arms, "consult")

    def test_an_ablation_names_its_dropped_references_in_the_job_label(self):
        args = parse(["--tier", "fast", "--drop-references", "security,code-review"])
        self.assertIn("-norefs-code-review+security", run.job_label(args))

    def test_an_ablation_cannot_save_a_baseline(self):
        """The release tier saves one by default; an ablation saved there would replace the full pack's."""
        with redirect_stderr(io.StringIO()) as err, self.assertRaises(SystemExit):
            parse(["--tier", "release", "--agent", "claude-code", "--drop-references", "security"])
        self.assertIn("an ablation never saves a baseline", err.getvalue())

    def test_dropping_references_from_a_skill_without_any_is_rejected(self):
        with redirect_stderr(io.StringIO()) as err, self.assertRaises(SystemExit):
            parse(["--tier", "fast", "--drop-references", "debugging"])
        self.assertIn("no references/ dir: debugging", err.getvalue())


class ArmConfigTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.runs = Path(self._tmp.name)
        patcher = mock.patch.object(run, "RUNS_DIR", self.runs)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.skills = run.frozen_skills()

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def agent(self, arm: str) -> dict:
        return run.build_job(JOB_ARGS, arm, "stamp", ["api-error-contract"], AGENT, HOOK, self.skills)["agents"][0]

    def test_dropped_references_leave_only_the_consult_arm(self):
        ablated = run.frozen_skills(("security",))
        consult = stub.skill_files(Path(ablated["consult"][0]))
        self.assertFalse([path for path in consult if path.startswith("security/references/")])
        self.assertIn("security/SKILL.md", consult)
        self.assertIn("api/references/pagination.md", consult)
        self.assertEqual(ablated["stub"], self.skills["stub"])
        self.assertNotEqual(ablated["consult"], self.skills["consult"])

    def test_the_stub_arm_installs_the_stub_skills_and_the_hook(self):
        agent = self.agent("stub")
        skills = Path(agent["skills"][0])
        self.assertEqual(skills.parent, self.runs / "stub-skills")
        self.assertTrue((skills / "workflow" / "SKILL.md").is_file())
        self.assertEqual(agent["kwargs"]["config"], HOOK)

    def test_the_stub_arm_differs_from_consult_only_in_its_skills_dir(self):
        stub_agent, consult_agent = self.agent("stub"), self.agent("consult")
        self.assertNotEqual(stub_agent.pop("skills"), consult_agent.pop("skills"))
        self.assertEqual(stub_agent, consult_agent)

    def test_the_bare_arm_gets_neither_skills_nor_the_hook(self):
        agent = self.agent("bare")
        self.assertEqual(agent["skills"], [])
        self.assertNotIn("config", agent["kwargs"])


class ReportTests(unittest.TestCase):
    def test_lift_gets_the_stub_job_when_the_stub_arm_ran(self):
        args = argparse.Namespace(save_baseline=None, no_lift=False, install_only=False)
        job_dirs = {arm: Path("/runs") / arm for arm in run.ARMS}
        with mock.patch.object(run.subprocess, "run", return_value=subprocess.CompletedProcess([], 0)) as lift_call:
            run.report(args, job_dirs, None, {})
        self.assertEqual(lift_call.call_args.args[0][-4:], ["/runs/bare", "/runs/consult", "--stub", "/runs/stub"])

    def test_the_saved_baseline_records_the_stub_job(self):
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(baseline, "BASELINES_DIR", Path(tmp)):
            job_dirs = {arm: Path(tmp) / arm for arm in run.ARMS}
            for job_dir in job_dirs.values():
                write_result(job_dir / "t__1", {"reward": 0.5})
            with redirect_stdout(io.StringIO()):
                run.save_baseline("release-claude-code", {}, job_dirs)
            self.assertEqual(baseline.load("release-claude-code")["stub"], str(Path(tmp) / "stub"))


class StubFailureBaselineTests(unittest.TestCase):
    """Bare and consult are complete; one stub trial has no reward."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        root = Path(self._tmp.name)
        patcher = mock.patch.object(baseline, "BASELINES_DIR", root / "baselines")
        patcher.start()
        self.addCleanup(patcher.stop)
        self.job_dirs = {arm: root / arm for arm in run.ARMS}
        write_result(self.job_dirs["bare"] / "t__1", {"reward": 0.5})
        write_result(self.job_dirs["consult"] / "t__1", {"reward": 0.6})
        write_result(self.job_dirs["stub"] / "t__1", None)
        self.stderr = io.StringIO()
        with redirect_stdout(io.StringIO()), redirect_stderr(self.stderr):
            run.save_baseline("release-claude-code", {"tasks": {}}, self.job_dirs)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_a_stub_trial_without_a_reward_leaves_the_baseline_reusable(self):
        with redirect_stdout(io.StringIO()):
            reuse = run.reusable_baseline("release-claude-code", {"tasks": {}})
        self.assertEqual((reuse["bare"], reuse["consult"]), (str(self.job_dirs["bare"]), str(self.job_dirs["consult"])))

    def test_an_incomplete_stub_job_is_left_out_of_the_baseline(self):
        self.assertNotIn("stub", baseline.load("release-claude-code"))
        self.assertIn("stub job left out, no reward for t__1", self.stderr.getvalue())

    def test_a_job_without_trials_is_not_saved_as_a_baseline(self):
        empty = {**self.job_dirs, "bare": self.job_dirs["bare"].parent / "never-started"}
        stderr = io.StringIO()
        with redirect_stdout(io.StringIO()), redirect_stderr(stderr):
            run.save_baseline("dry-run", {"tasks": {}}, empty)
        self.assertIsNone(baseline.load("dry-run"))
        self.assertIn("no trials in bare", stderr.getvalue())


class SkillSnapshotTests(unittest.TestCase):
    """A run whose skills source gets a description edit once the stub arm has started."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.source = self.root / "skills"
        shutil.copytree(run.SKILLS_DIR, self.source)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def fake_harbor(self, config_path: Path, extra: list[str], host_env: dict) -> Path:
        if config_path.name.endswith("-stub.job.json"):
            skill_md = self.source / "proof" / "SKILL.md"
            skill_md.write_bytes(skill_md.read_bytes().replace(b"description: ", b"description: Edited. ", 1))
        return self.root / "runs" / json.loads(config_path.read_text())["job_name"]

    def arm_skills(self, arm: str) -> str:
        config = json.loads(next((self.root / "runs").glob(f"*-{arm}.job.json")).read_text())
        return config["agents"][0]["skills"][0]

    def test_a_skill_edit_during_the_run_reaches_neither_arm(self):
        argv = ["run.py", "--suite", "rules", "--agent", "claude-code", "--arms", "bare,stub,consult",
                "--skip-preflight", "--no-lift"]
        with mock.patch.multiple(run, SKILLS_DIR=self.source, RUNS_DIR=self.root / "runs",
                                 tier_tasks=lambda args: ["api-error-contract"],
                                 load_agent=lambda name, model: (AGENT, {}, HOOK), start_job=self.fake_harbor), \
                mock.patch.object(sys, "argv", argv), redirect_stdout(io.StringIO()):
            run.main()
        self.assertEqual(frontmatter(self.arm_skills("consult"), "proof"), frontmatter(self.arm_skills("stub"), "proof"))


class SelectionTests(unittest.TestCase):
    def test_a_changed_skill_file_maps_to_its_skill(self):
        self.assertEqual(selection.skill_name("agents/.agents/skills/api/references/errors.md"), "api")
        self.assertIsNone(selection.skill_name("agents/.agents/README.md"))

    def test_tasks_where_the_skill_is_most_central_come_first(self):
        tasks = selection.select_tasks({"ui-design"}, ["service-from-brief", "accessible-ui-state", "api-error-contract"], 4)
        self.assertEqual(tasks, ["accessible-ui-state", "service-from-brief"])

    def test_a_task_that_only_scores_the_skill_rules_is_selected(self):
        self.assertEqual(selection.select_tasks({"documentation"}, ["bug-from-symptom"], 4), ["bug-from-symptom"])

    def test_selection_stops_at_the_limit(self):
        candidates = ["proof-first-bugfix", "proof-pipeline-shape", "proof-validator-error-content"]
        self.assertEqual(len(selection.select_tasks({"proof"}, candidates, 2)), 2)


class BaselineTests(unittest.TestCase):
    def test_a_matching_key_is_reusable_for_a_subset_of_its_tasks(self):
        stored = baseline.baseline_key(AGENT, None, ["proof-first-bugfix", "api-error-contract"])
        self.assertIsNone(baseline.mismatch(stored, baseline.baseline_key(AGENT, None, ["api-error-contract"])))

    def test_a_different_model_is_not_reusable(self):
        stored = baseline.baseline_key(AGENT, None, ["api-error-contract"])
        current = baseline.baseline_key({**AGENT, "model_name": "anthropic/claude-haiku-4-5"}, None, ["api-error-contract"])
        self.assertIn("model differs", baseline.mismatch(stored, current))

    def test_a_task_the_baseline_never_ran_is_not_reusable(self):
        stored = baseline.baseline_key(AGENT, None, ["api-error-contract"])
        current = baseline.baseline_key(AGENT, None, ["proof-first-bugfix"])
        self.assertIn("no run of proof-first-bugfix", baseline.mismatch(stored, current))

    def test_a_trial_without_a_reward_blocks_the_baseline(self):
        with tempfile.TemporaryDirectory() as tmp:
            job = Path(tmp)
            for name, rewards in (("ok__1", {"reward": 0.7}), ("failed__1", None)):
                (job / name).mkdir()
                (job / name / "result.json").write_text(json.dumps({"verifier_result": rewards and {"rewards": rewards}}))
            self.assertEqual(baseline.unrewarded_trials(job), ["failed__1"])

    def test_editing_any_task_file_changes_its_hash(self):
        with tempfile.TemporaryDirectory() as tmp:
            task = Path(tmp) / "t"
            shutil.copytree(EVAL_DIR / "tasks" / "api-error-contract", task)
            before = baseline.task_hash(task)
            (task / "tests" / "hidden.mjs").write_text("// changed\n")
            self.assertNotEqual(before, baseline.task_hash(task))


if __name__ == "__main__":
    unittest.main()
