"""The offline rescorer: bundle parsing, workspace rebuild, reward merge, and the job layout lift.py reads.

  python3 -m unittest discover eval/verifier/tests

Docker is stubbed: build_scaffold copies a fixture repository and run_container
writes the verifier outputs a real run would, with the bundle rebuilt by
consult_lib.build_bundle from the rebuilt workspace.
"""

from __future__ import annotations

import io
import json
import os
import shutil
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from datetime import UTC, datetime
from pathlib import Path
from unittest import mock

EVAL_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(EVAL_DIR / "scripts"))
sys.path.insert(0, str(EVAL_DIR / "verifier" / "shared"))

import consult_lib
import lift
import rescore

# zz-last.txt sorts last in the diff; its hunk ends in blank context lines that build_bundle strips.
SCAFFOLD_FILES = {
    "src/app.js": "export const limit = 1;\n",
    "old.txt": "remove me\n",
    "zz-last.txt": "a\nb\nc\nd\n\n\n\n",
}
OLD_REWARDS = {"verification": 0.0, "proof": 0.15, "change_quality": 1.0, "judge": 1.0, "reward": 0.3}
NEW_REWARDS = {"verification": 1.0, "proof": 1.0, "change_quality": 1.0, "rules": 1.0, "reward": 1.0}
NEW_DETAILS = {"rules": {"score": 1.0, "criteria": [{"name": "api.1", "value": 1.0}]}}
CODE_WEIGHTS = {
    "verification": 0.275,
    "proof": 0.1925,
    "change_quality": 0.0825,
    "judge": 0.45,
    "skill_triggering": 0.0,
    "non_interruption": 0.0,
    "rules": 0.0,
}


def git(repo: Path, *args: str) -> None:
    proc = rescore.git(repo, "-c", "user.name=eval", "-c", "user.email=eval@example.com", *args)
    if proc.returncode:
        raise AssertionError(proc.stderr)


def make_scaffold(path: Path, files: dict[str, str]) -> Path:
    """The Dockerfile's scaffold: the workspace committed once, node_modules excluded."""
    for rel, content in files.items():
        (path / rel).parent.mkdir(parents=True, exist_ok=True)
        (path / rel).write_text(content)
    git(path, "init", "-q")
    git(path, "add", "-A")
    git(path, "commit", "-qm", "scaffold")
    with (path / ".git" / "info" / "exclude").open("a") as exclude:
        exclude.write("node_modules/\n")
    return path


def agent_changes(workspace: Path) -> None:
    """Edits, a deletion, a file added to git, and an untracked file with its own code fence and heading."""
    (workspace / "src" / "app.js").write_text("export const limit = 2;\n")
    (workspace / "old.txt").unlink()
    (workspace / "zz-last.txt").write_text("a\nb\nc\nD\n\n\n\n")
    (workspace / "src" / "new.js").write_text("export const added = true;\n")
    git(workspace, "add", "src/new.js")
    (workspace / "docs").mkdir()
    (workspace / "docs" / "NOTES.md").write_text("# Notes\n\n```\ncode\n```\n\n## Next\n")


def fake_verifier(trial: rescore.Trial, workspace: Path, final_dest: Path, rejudge: bool = False) -> list[str]:
    verifier = final_dest / "verifier"
    (verifier / "judge-bundle.md").write_text(consult_lib.build_bundle(workspace))
    (verifier / "reward.json").write_text(json.dumps(NEW_REWARDS))
    (verifier / "reward-details.json").write_text(json.dumps(NEW_DETAILS))
    return []


def root_owned_verifier(trial: rescore.Trial, workspace: Path, final_dest: Path, rejudge: bool = False) -> list[str]:
    """On Linux with rootful Docker the verifier's files are root-owned 0644, which the host user cannot write."""
    fake_verifier(trial, workspace, final_dest)
    for name in ("reward.json", "reward-details.json"):
        (final_dest / "verifier" / name).chmod(0o444)
    return []


def started_now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


class RescoreTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name).resolve()
        env = mock.patch.dict(os.environ, rescore.GIT_ENV)
        env.start()
        self.addCleanup(env.stop)
        self.scaffold = make_scaffold(self.root / "scaffold", SCAFFOLD_FILES)
        agent = self.root / "agent-workspace"
        shutil.copytree(self.scaffold, agent)
        agent_changes(agent)
        self.bundle = consult_lib.build_bundle(agent)

    def tearDown(self) -> None:
        self._tmp.cleanup()


class BundleTests(RescoreTestCase):
    def test_a_rebuilt_workspace_gives_back_the_bundle_the_judge_read(self):
        rebuilt = self.root / "rebuilt"
        shutil.copytree(self.scaffold, rebuilt)
        rescore.reconstruct(rebuilt, rescore.parse_bundle(self.bundle))
        self.assertEqual(consult_lib.build_bundle(rebuilt), self.bundle)

    def test_a_truncated_bundle_is_rejected(self):
        truncated = self.bundle[: self.bundle.index("## Final agent message")]
        with self.assertRaisesRegex(rescore.RebuildError, "truncated"):
            rescore.parse_bundle(truncated)

    def test_a_diff_that_does_not_apply_is_rejected(self):
        other = make_scaffold(self.root / "other", {**SCAFFOLD_FILES, "src/app.js": "export const limit = 9;\n"})
        with self.assertRaisesRegex(rescore.RebuildError, "does not apply"):
            rescore.reconstruct(other, rescore.parse_bundle(self.bundle))


class TestDirTests(unittest.TestCase):
    def dirs(self, steps: tuple[str, ...]) -> list[Path]:
        trial = rescore.Trial(job=Path("job"), dir=Path("job/t"), task="money-field-change", steps=steps, result={})
        return rescore.test_dirs(trial)

    def test_a_trial_recorded_before_its_task_gained_a_step_gets_the_shared_tests(self):
        """Its last step is now a middle step, whose own tests are an unscored placeholder."""
        self.assertEqual(self.dirs(("brief", "approve")), [rescore.TASKS_DIR / "money-field-change" / "tests"])

    def test_a_trial_that_ended_on_the_brief_step_keeps_its_sign_off_suite(self):
        task = rescore.TASKS_DIR / "money-field-change"
        self.assertEqual(self.dirs(("brief",)), [task / "tests", task / "steps" / "brief" / "tests"])


class MergeTests(unittest.TestCase):
    def test_the_recorded_reward_is_the_weighted_mean_of_its_dimensions(self):
        recorded = {
            "change_quality": 1.0,
            "judge": 0.8355,
            "non_interruption": 1.0,
            "proof": 0.15,
            "rules": 1.0,
            "skill_triggering": 0.5,
            "verification": 0.0,
        }
        self.assertEqual(rescore.weighted_reward(recorded, CODE_WEIGHTS), 0.4874)

    def test_the_merged_reward_keeps_the_original_judge_score(self):
        new = {"verification": 1.0, "proof": 1.0, "change_quality": 1.0, "reward": 1.0}
        merged = rescore.merge_rewards({**OLD_REWARDS, "judge": 0.8}, new, CODE_WEIGHTS)
        self.assertEqual(merged["judge"], 0.8)
        self.assertAlmostEqual(merged["reward"], 0.55 + 0.45 * 0.8, places=4)

    def test_an_old_judge_score_keeps_its_share_under_the_rubric_weights(self):
        """The task's reward.toml now weighs rubric, not judge; the old judge takes the rubric's 0.45."""
        rubric_weights = {("rubric" if d == "judge" else d): w for d, w in CODE_WEIGHTS.items()}
        new = {"verification": 1.0, "proof": 1.0, "change_quality": 1.0, "reward": 1.0}
        merged = rescore.merge_rewards({**OLD_REWARDS, "judge": 0.8}, new, rubric_weights)
        self.assertEqual(merged["judge"], 0.8)
        self.assertAlmostEqual(merged["reward"], 0.55 + 0.45 * 0.8, places=4)

    def test_a_rubric_score_is_kept_like_a_judge_score(self):
        rubric_weights = {("rubric" if d == "judge" else d): w for d, w in CODE_WEIGHTS.items()}
        new = {"verification": 1.0, "proof": 1.0, "change_quality": 1.0, "rubric": 0.0, "reward": 1.0}
        merged = rescore.merge_rewards({"rubric": 0.5, "reward": 0.3}, new, rubric_weights)
        self.assertEqual(merged["rubric"], 0.5)
        self.assertAlmostEqual(merged["reward"], 0.55 + 0.45 * 0.5, places=4)

    def test_a_trial_whose_verifier_skipped_the_judge_is_rewarded_on_its_deterministic_dimensions(self):
        new = {"verification": 0.0, "proof": 1.0, "change_quality": 1.0, "reward": 0.5}
        merged = rescore.merge_rewards({"verification": 0.0, "reward": 0.1}, new, CODE_WEIGHTS)
        self.assertNotIn("judge", merged)
        self.assertAlmostEqual(merged["reward"], 0.275 / 0.55, places=4)


class KeepJudgeAnswersTests(unittest.TestCase):
    def test_the_judges_answers_and_transcripts_follow_the_kept_score(self):
        with tempfile.TemporaryDirectory() as tmp:
            original, new = Path(tmp) / "original", Path(tmp) / "new"
            (original / "judge").mkdir(parents=True)
            (original / "judge-items.json").write_text('{"score": 0.5}')
            (original / "judge" / "scope.1.jsonl").write_text("{}\n")
            new.mkdir()
            rescore.keep_judge_answers(original, new)
            self.assertEqual((new / "judge-items.json").read_text(), '{"score": 0.5}')
            self.assertTrue((new / "judge" / "scope.1.jsonl").is_file())

    def test_a_trial_without_rubric_judges_copies_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            original, new = Path(tmp) / "original", Path(tmp) / "new"
            original.mkdir()
            new.mkdir()
            rescore.keep_judge_answers(original, new)
            self.assertEqual(list(new.iterdir()), [])


class JobTestCase(RescoreTestCase):
    """A job dir of saved trials, and the rescorer run on it with Docker stubbed."""

    def setUp(self) -> None:
        super().setUp()
        self.job = self.root / "consult-job"
        self.out = self.root / "consult-job-rescored"

    def single_step(self, name: str, bundle: str, **result_fields) -> None:
        trial = self.job / name
        (trial / "verifier").mkdir(parents=True)
        (trial / "agent").mkdir()
        (trial / "agent" / "trajectory.json").write_text(json.dumps({"steps": []}))
        (trial / "verifier" / "judge-bundle.md").write_text(bundle)
        (trial / "verifier" / "reward-details.json").write_text(json.dumps({"judge": {"score": 1.0}}))
        result = {
            "task_name": "consult/api-error-contract",
            "verifier_result": {"rewards": OLD_REWARDS},
            "started_at": started_now(),
            **result_fields,
        }
        (trial / "result.json").write_text(json.dumps(result))

    def multi_step(self, name: str) -> None:
        trial = self.job / name
        for step in ("brief", "approve"):
            (trial / "steps" / step / "verifier").mkdir(parents=True)
            (trial / "steps" / step / "agent").mkdir()
        brief = {"signoff": {"criteria": [{"name": "mode_built", "value": 1.0}]}}
        (trial / "steps" / "brief" / "verifier" / "reward-details.json").write_text(json.dumps(brief))
        (trial / "steps" / "approve" / "verifier" / "judge-bundle.md").write_text(self.bundle)
        steps = [
            {"step_name": "brief", "verifier_result": {"rewards": {"signoff": 1.0, "reward": 1.0}}},
            {"step_name": "approve", "verifier_result": {"rewards": OLD_REWARDS}},
        ]
        result = {
            "task_name": "consult/money-field-change",
            "verifier_result": {"rewards": OLD_REWARDS},
            "started_at": started_now(),
            "step_results": steps,
        }
        (trial / "result.json").write_text(json.dumps(result))

    def copy_scaffold(self, task: str, dest: Path) -> Path:
        return Path(shutil.copytree(self.scaffold, dest))

    def run_cli(self, *extra: str, verifier=fake_verifier) -> int:
        with (
            mock.patch.object(rescore, "build_scaffold", self.copy_scaffold),
            mock.patch.object(rescore, "run_container", side_effect=verifier) as container,
            redirect_stdout(io.StringIO()),
        ):
            code = rescore.main(["rescore.py", str(self.job), *extra])
        self.container = container
        return code


class RescoredJobTests(JobTestCase):
    def test_lift_reads_a_rescored_job(self):
        self.single_step("api-error-contract__a", self.bundle)
        self.multi_step("money-field-change__b")
        self.assertEqual(self.run_cli(), 0)
        by_task = lift.load_trials(self.out)
        single, multi = by_task["consult/api-error-contract"][0], by_task["consult/money-field-change"][0]
        self.assertEqual((single["reward"], single["rewards"]["judge"], single["rules"]), (1.0, 1.0, {"api.1": 1.0}))
        self.assertEqual((multi["reward"], multi["signoff_mode"]), (1.0, "built"))
        self.assertEqual(lift.summarize(by_task, by_task)["tasks"][0]["consult"], 1.0)

    def test_a_trial_whose_bundle_does_not_rebuild_reaches_lift_as_failed(self):
        self.single_step("api-error-contract__a", self.bundle[: self.bundle.index("## Final agent message")])
        self.assertEqual(self.run_cli(), 1)
        entry = lift.load_trials(self.out)["consult/api-error-contract"][0]
        self.assertEqual((entry["error"], entry["reward"]), ("RescoreError", None))
        self.assertIn("truncated", json.loads((self.out / "rescore.json").read_text())["trials"][0]["flags"][0])

    def test_a_rebuilt_bundle_that_differs_from_the_judged_one_is_not_scored(self):
        judged = self.bundle.replace("No final message was captured.", "Done.")
        self.single_step("api-error-contract__a", judged)
        self.assertEqual(self.run_cli(), 1)
        entry = lift.load_trials(self.out)["consult/api-error-contract"][0]
        self.assertEqual((entry["error"], entry["reward"]), ("RescoreError", None))

    def test_a_trial_whose_original_verifier_recorded_no_reward_is_not_scored(self):
        crashed = {"exception_type": "RewardFileNotFoundError", "exception_message": "judge rate limited"}
        self.single_step("api-error-contract__a", self.bundle, verifier_result=None, exception_info=crashed)
        self.assertEqual(self.run_cli(), 1)
        entry = lift.load_trials(self.out)["consult/api-error-contract"][0]
        self.assertEqual((entry["error"], entry["reward"]), ("RescoreError", None))
        self.assertIn("no reward", json.loads((self.out / "rescore.json").read_text())["trials"][0]["flags"][0])

    def test_a_trial_that_started_before_its_task_environment_changed_is_not_scored(self):
        self.single_step("api-error-contract__a", self.bundle, started_at="2000-01-01T00:00:00.000000Z")
        self.assertEqual(self.run_cli(), 1)
        entry = lift.load_trials(self.out)["consult/api-error-contract"][0]
        self.assertEqual((entry["error"], entry["reward"]), ("RescoreError", None))
        self.assertIn("environment", json.loads((self.out / "rescore.json").read_text())["trials"][0]["flags"][0])

    def test_verifier_outputs_the_host_user_cannot_write_are_replaced(self):
        self.single_step("api-error-contract__a", self.bundle)
        self.assertEqual(self.run_cli(verifier=root_owned_verifier), 0)
        entry = lift.load_trials(self.out)["consult/api-error-contract"][0]
        self.assertEqual((entry["reward"], entry["rewards"]["judge"]), (1.0, 1.0))

    def test_the_tasks_filter_rescores_only_the_named_tasks(self):
        self.single_step("api-error-contract__a", self.bundle)
        self.multi_step("money-field-change__b")
        self.run_cli("--tasks", "money-field-change")
        self.assertEqual(sorted(lift.load_trials(self.out)), ["consult/money-field-change"])

    def test_a_dry_run_runs_no_verifier_and_writes_nothing(self):
        self.single_step("api-error-contract__a", self.bundle)
        self.assertEqual(self.run_cli("--dry-run"), 0)
        self.container.assert_not_called()
        self.assertFalse(self.out.exists())


RUBRIC_REWARDS = {"verification": 1.0, "proof": 1.0, "change_quality": 1.0, "rubric": 0.8, "reward": 0.91}


def judging_verifier(trial: rescore.Trial, workspace: Path, final_dest: Path, rejudge: bool = False) -> list[str]:
    """A live verifier: the rubric judges answered, and the reward carries their score."""
    fake_verifier(trial, workspace, final_dest)
    (final_dest / "verifier" / "reward.json").write_text(json.dumps(RUBRIC_REWARDS))
    (final_dest / "verifier" / "judge-items.json").write_text(json.dumps({"score": 0.8, "items": []}))
    return []


def failed_judge_verifier(trial: rescore.Trial, workspace: Path, final_dest: Path, rejudge: bool = False) -> list[str]:
    """The judges failed, so the runner dropped the rubric and the reward has no rubric score."""
    fake_verifier(trial, workspace, final_dest)
    (final_dest / "verifier" / "judge-items.json").write_text(json.dumps({"score": None, "items": []}))
    return []


class RejudgeTests(JobTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.out = self.root / "consult-job-rejudged"
        token = mock.patch.dict(os.environ, {"CLAUDE_CODE_OAUTH_TOKEN": "test-token"})
        token.start()
        self.addCleanup(token.stop)

    def test_without_yes_it_states_the_judge_calls_and_runs_nothing(self):
        self.single_step("api-error-contract__a", self.bundle)
        out = io.StringIO()
        with redirect_stdout(out):
            code = rescore.main(["rescore.py", str(self.job), "--rejudge"])
        calls = rescore.rubric_calls("api-error-contract")
        self.assertEqual(code, 0)
        self.assertIn(f"1 trials, {calls} judge calls (up to {2 * calls} with retries)", out.getvalue())
        self.assertFalse(self.out.exists())

    def test_yes_without_a_token_refuses(self):
        self.single_step("api-error-contract__a", self.bundle)
        with mock.patch.dict(os.environ, {"CLAUDE_CODE_OAUTH_TOKEN": ""}), mock.patch("sys.stderr", io.StringIO()):
            self.assertEqual(self.run_cli("--rejudge", "--yes", verifier=judging_verifier), 2)
        self.container.assert_not_called()

    def test_a_rejudged_trial_takes_the_new_rubric_score_and_drops_the_old_judge(self):
        self.single_step("api-error-contract__a", self.bundle)
        self.assertEqual(self.run_cli("--rejudge", "--yes", verifier=judging_verifier), 0)
        entry = lift.load_trials(self.out)["consult/api-error-contract"][0]
        self.assertEqual(entry["rewards"], RUBRIC_REWARDS)
        self.assertTrue((self.out / "api-error-contract__a" / "verifier" / "judge-items.json").is_file())
        self.assertTrue(self.container.call_args.args[3])

    def test_a_trial_whose_original_verifier_recorded_no_reward_can_be_rejudged(self):
        crashed = {"exception_type": "RewardFileNotFoundError", "exception_message": "judge rate limited"}
        self.single_step("api-error-contract__a", self.bundle, verifier_result=None, exception_info=crashed)
        self.assertEqual(self.run_cli("--rejudge", "--yes", verifier=judging_verifier), 0)
        self.assertEqual(lift.load_trials(self.out)["consult/api-error-contract"][0]["reward"], 0.91)

    def test_a_failed_judge_keeps_the_deterministic_reward_and_says_so(self):
        self.single_step("api-error-contract__a", self.bundle)
        self.assertEqual(self.run_cli("--rejudge", "--yes", verifier=failed_judge_verifier), 0)
        row = json.loads((self.out / "rescore.json").read_text())["trials"][0]
        self.assertEqual(row["new"], NEW_REWARDS)
        self.assertIn(rescore.RUBRIC_DROPPED, row["notes"])

    def test_a_verifier_that_left_no_judge_answers_is_not_scored(self):
        self.single_step("api-error-contract__a", self.bundle)
        self.assertEqual(self.run_cli("--rejudge", "--yes"), 1)
        self.assertIn("judge-items.json", json.loads((self.out / "rescore.json").read_text())["trials"][0]["flags"][0])

    def test_a_task_without_a_rubric_is_not_rejudged(self):
        self.single_step("routing-settings-copy__a", self.bundle, task_name="consult/routing-settings-copy")
        self.assertEqual(self.run_cli("--rejudge", "--yes", verifier=judging_verifier), 1)
        self.container.assert_not_called()
        self.assertIn("no rubric", json.loads((self.out / "rescore.json").read_text())["trials"][0]["flags"][0])

    def test_a_repeat_pass_writes_beside_the_first(self):
        self.single_step("api-error-contract__a", self.bundle)
        self.run_cli("--rejudge", "--yes", "--suffix", "rejudged-repeat", verifier=judging_verifier)
        self.assertTrue((self.root / "consult-job-rejudged-repeat" / "rescore.json").is_file())

    def test_rejudging_runs_one_trial_at_a_time(self):
        with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            rescore.parse_args([str(self.job), "--rejudge", "--concurrency", "2"])
        self.assertEqual(rescore.parse_args([str(self.job), "--rejudge"]).concurrency, 1)

    def test_the_token_reaches_the_container_by_name_only(self):
        self.assertEqual(rescore.verifier_env(rejudge=True), ["-e", "CLAUDE_CODE_OAUTH_TOKEN"])
        self.assertEqual(rescore.verifier_env(rejudge=False), ["-e", "CONSULT_EVAL_SKIP_JUDGE=1"])


class EnvironmentChangedTests(unittest.TestCase):
    """A fresh checkout writes every file now; the last commit says when the environment really changed."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        repo = Path(self._tmp.name).resolve()
        env = mock.patch.dict(os.environ, {**rescore.GIT_ENV, "GIT_COMMITTER_DATE": "2001-01-01T00:00:00Z"})
        env.start()
        self.addCleanup(env.stop)
        self.dockerfile = repo / "tasks" / "t" / "environment" / "Dockerfile"
        self.dockerfile.parent.mkdir(parents=True)
        self.dockerfile.write_text("FROM node:22\n")
        git(repo, "init", "-q")
        git(repo, "add", "-A")
        git(repo, "commit", "-qm", "environment")
        for name, value in (("EVAL_DIR", repo), ("TASKS_DIR", repo / "tasks")):
            patch = mock.patch.object(rescore, name, value)
            patch.start()
            self.addCleanup(patch.stop)

    def test_a_clean_environment_changed_when_it_was_last_committed(self):
        self.assertEqual(rescore.environment_changed_at("t"), datetime(2001, 1, 1, tzinfo=UTC).timestamp())

    def test_an_uncommitted_change_counts_from_its_file_time(self):
        self.dockerfile.write_text("FROM node:24\n")
        self.assertGreater(rescore.environment_changed_at("t"), datetime(2020, 1, 1, tzinfo=UTC).timestamp())


if __name__ == "__main__":
    unittest.main()
