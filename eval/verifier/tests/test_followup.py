"""The follow-up change test: its hidden check against the oracle, the task builder, and the report.

  python3 -m unittest discover eval/verifier/tests

The hidden check runs as consult_lib.hidden_check_passes runs it, on the
staged-commissions reference (steps/s1-approve/solution/reference) and on that
reference with the follow-up oracle (followup/staged-commissions/solution/overlay)
copied over it. It needs Node 22 and npm, which installs the reference's
lockfile once. Docker is stubbed for the builder: build_scaffolds returns the
task's workspace committed in git, as the task image holds it.
"""

from __future__ import annotations

import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest import mock

EVAL_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(EVAL_DIR / "scripts"))
sys.path.insert(0, str(EVAL_DIR / "verifier" / "shared"))

import consult_lib
import followup
import rescore

TASK_DIR = EVAL_DIR / "tasks" / "staged-commissions"
SCAFFOLD = TASK_DIR / "environment" / "workspace"
REFERENCE = TASK_DIR / "steps" / "s1-approve" / "solution" / "reference"
ORACLE = followup.FOLLOWUP_DIR / "solution" / "overlay"
HIDDEN = followup.HIDDEN_DIR / "staged-commissions-followup.mjs"
STAGES = followup.HIDDEN_DIR / "staged-commissions.mjs"
NEEDS_NODE = "the hidden check needs node and npm on PATH"


def last_json(stdout: str) -> dict:
    return json.loads(stdout.strip().splitlines()[-1])


@unittest.skipUnless(shutil.which("node") and shutil.which("npm"), NEEDS_NODE)
class FollowupCheckTests(unittest.TestCase):
    """The oracle passes all six stages; the stage-5 reference passes 1 to 5 and fails 6."""

    @classmethod
    def setUpClass(cls) -> None:
        cls._tmp = tempfile.TemporaryDirectory()
        cls.deps = Path(cls._tmp.name) / "deps"
        cls.deps.mkdir()
        for name in ("package.json", "package-lock.json"):
            shutil.copy2(REFERENCE / name, cls.deps / name)
        subprocess.run(
            ["npm", "ci", "--no-audit", "--no-fund", "--prefer-offline", "--loglevel=error"],
            cwd=cls.deps,
            check=True,
            capture_output=True,
            timeout=300,
        )

    @classmethod
    def tearDownClass(cls) -> None:
        cls._tmp.cleanup()

    def run_check(self, *overlays: Path, edit: tuple[str, str, str] | None = None) -> subprocess.CompletedProcess[str]:
        workspace = Path(tempfile.mkdtemp(dir=self._tmp.name)) / "app"
        shutil.copytree(SCAFFOLD, workspace)
        for overlay in overlays:
            shutil.copytree(overlay, workspace, dirs_exist_ok=True)
        if edit:
            path, old, new = edit
            text = (workspace / path).read_text()
            self.assertEqual(text.count(old), 1, f"edit does not apply to {path}")
            (workspace / path).write_text(text.replace(old, new))
        (workspace / "node_modules").symlink_to(self.deps / "node_modules")
        return subprocess.run(
            ["node", "--input-type=module", "-e", HIDDEN.read_text()],
            cwd=workspace,
            env={**os.environ, "STAGES_CHECK": str(STAGES)},
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )

    def test_the_oracle_passes_all_six_stages(self):
        result = self.run_check(REFERENCE, ORACLE)

        self.assertEqual(result.returncode, 0, result.stderr[-1500:])
        self.assertEqual(last_json(result.stdout), {f"s{n}": 1 for n in range(1, 7)})

    def test_the_stage_five_reference_passes_stages_one_to_five_and_fails_stage_six(self):
        result = self.run_check(REFERENCE)

        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(last_json(result.stdout), {**{f"s{n}": 1 for n in range(1, 6)}, "s6": 0})
        self.assertIn("s6: returning total", result.stderr)

    def test_counting_a_dispatch_as_a_delivery_fails_stage_six(self):
        edit = ("src/commissions/store.ts", "status = 'delivered'", "status IN ('dispatched', 'delivered')")

        result = self.run_check(REFERENCE, ORACLE, edit=edit)

        self.assertEqual(last_json(result.stdout)["s6"], 0)
        self.assertIn("placed while the first is dispatched", result.stderr)


# ------------------------------------------------------------------- builder and report


def git(repo: Path, *args: str) -> None:
    proc = rescore.git(repo, "-c", "user.name=eval", "-c", "user.email=eval@example.com", *args)
    if proc.returncode:
        raise AssertionError(proc.stderr)


def committed_copy(source: Path, dest: Path) -> Path:
    """The Dockerfile's scaffold: the workspace committed once, node_modules excluded."""
    shutil.copytree(source, dest)
    git(dest, "init", "-q")
    git(dest, "add", "-A")
    git(dest, "commit", "-qm", "scaffold")
    with (dest / ".git" / "info" / "exclude").open("a") as exclude:
        exclude.write("node_modules/\n")
    return dest


def bundle_after(scaffold: Path, dest: Path, files: dict[str, str]) -> str:
    """judge-bundle.md for a copy of the scaffold with these files written (edits and new files)."""
    shutil.copytree(scaffold, dest)
    for rel, text in files.items():
        (dest / rel).parent.mkdir(parents=True, exist_ok=True)
        (dest / rel).write_text(text)
    return consult_lib.build_bundle(dest)


def write_trial(job: Path, name: str, result: dict, bundle: str | None, final: Path) -> None:
    trial = job / name
    (trial / final / "verifier").mkdir(parents=True)
    (trial / "result.json").write_text(json.dumps(result))
    if bundle is not None:
        (trial / final / "verifier" / "judge-bundle.md").write_text(bundle)


def staged_result(verification: float, task: str = "consult/staged-commissions") -> dict:
    return {
        "task_name": task,
        "started_at": datetime.now(UTC).isoformat(),
        "step_results": [{"step_name": "s1-brief"}, {"step_name": "s5-continue"}],
        "verifier_result": {"rewards": {"verification": verification, "reward": verification}},
    }


class GitTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name).resolve()
        env = mock.patch.dict(os.environ, rescore.GIT_ENV)
        env.start()
        self.addCleanup(env.stop)


class BuildTests(GitTestCase):
    FINAL = Path("steps", "s5-continue")

    def setUp(self) -> None:
        super().setUp()
        self.scaffold = committed_copy(SCAFFOLD, self.root / "scaffold")
        bare_tree = bundle_after(self.scaffold, self.root / "bare-tree", {"src/main.ts": "// bare\n"})
        consult_tree = bundle_after(self.scaffold, self.root / "consult-tree", {"src/commissions/x.ts": "// consult\n"})
        self.bare_job, self.consult_job = self.root / "bare-job", self.root / "consult-job"
        write_trial(self.bare_job, "staged-commissions__Aa1", staged_result(1.0), bare_tree, self.FINAL)
        write_trial(self.bare_job, "staged-commissions__Bb2", staged_result(0.0), bare_tree, self.FINAL)
        write_trial(self.consult_job, "staged-commissions__Cc3", staged_result(1.0), consult_tree, self.FINAL)
        control = staged_result(1.0, "consult/follow-the-project")
        write_trial(self.consult_job, "follow-the-project__Dd4", control, consult_tree, Path())
        self.out = self.root / "followup"

    def build(self) -> str:
        stdout = io.StringIO()
        with (
            mock.patch.object(followup, "OUT_DIR", self.out),
            mock.patch.object(rescore, "build_scaffolds", return_value={"staged-commissions": self.scaffold}),
            redirect_stdout(stdout),
        ):
            code = followup.main(["followup.py", "build", str(self.bare_job), str(self.consult_job)])
        self.assertEqual(code, 0, stdout.getvalue())
        return stdout.getvalue()

    def built(self) -> dict[str, Path]:
        (stamp,) = self.out.iterdir()
        return {p.name: p for p in stamp.iterdir() if p.is_dir()}

    def test_one_task_per_passing_staged_trial_named_for_its_source_arm(self):
        self.build()

        tasks = self.built()
        self.assertEqual(sorted(tasks), ["bare-staged-commissions-aa1", "consult-staged-commissions-cc3"])
        toml = (tasks["consult-staged-commissions-cc3"] / "task.toml").read_text()
        self.assertIn('name = "consult/followup-consult-staged-commissions-cc3"', toml)
        self.assertIn('source_trial = "consult-job/staged-commissions__Cc3"', toml)
        self.assertNotIn("[[steps]]", toml)
        self.assertEqual(followup.source_arm("consult/followup-bare-staged-commissions-aa1"), "bare")

    def test_the_starting_tree_is_the_trials_final_tree_without_git(self):
        self.build()

        workspace = self.built()["consult-staged-commissions-cc3"] / "environment" / "workspace"
        self.assertEqual((workspace / "src" / "commissions" / "x.ts").read_text(), "// consult\n")
        self.assertEqual((workspace / "catalogue.json").read_text(), (SCAFFOLD / "catalogue.json").read_text())
        self.assertFalse((workspace / ".git").exists())

    def test_the_task_asks_for_the_sixth_change_and_carries_both_checks(self):
        self.build()

        task = self.built()["bare-staged-commissions-aa1"]
        instruction = (followup.FOLLOWUP_DIR / "instruction.md").read_text()
        self.assertEqual((task / "instruction.md").read_text(), instruction)
        self.assertEqual((task / "tests" / "hidden.mjs").read_bytes(), HIDDEN.read_bytes())
        self.assertEqual((task / "tests" / "stages.mjs").read_bytes(), STAGES.read_bytes())
        self.assertTrue(os.access(task / "tests" / "test.sh", os.X_OK))
        self.assertTrue((task / "tests" / "verification" / "verification.py").is_file())
        dockerfile = (TASK_DIR / "environment" / "Dockerfile").read_bytes()
        self.assertEqual((task / "environment" / "Dockerfile").read_bytes(), dockerfile)

    def test_the_job_runs_every_task_with_the_bare_arm(self):
        stdout = self.build()

        (stamp,) = self.out.iterdir()
        config = json.loads((stamp / "job.json").read_text())
        self.assertEqual(len(config["tasks"]), 2)
        (agent,) = config["agents"]
        self.assertEqual(agent["skills"], [])
        self.assertNotIn("config", agent["kwargs"])
        self.assertIn(f"harbor run -c {stamp / 'job.json'} --yes", stdout)

    def test_a_trial_whose_tree_cannot_be_rebuilt_is_skipped(self):
        (self.consult_job / "staged-commissions__Cc3" / self.FINAL / "verifier" / "judge-bundle.md").write_text("junk")

        stdout = self.build()

        self.assertEqual(sorted(self.built()), ["bare-staged-commissions-aa1"])
        self.assertIn("skipped consult-job/staged-commissions__Cc3", stdout)


def followup_result(task: str, verification: float | None, tokens: int, seconds: int) -> dict:
    start = datetime(2026, 11, 11, tzinfo=UTC)
    result: dict = {
        "task_name": f"consult/followup-{task}",
        "agent_result": {"n_output_tokens": tokens},
        "agent_execution": {
            "started_at": start.isoformat(),
            "finished_at": (start + timedelta(seconds=seconds)).isoformat(),
        },
        "verifier_result": None,
    }
    if verification is None:
        result["exception_info"] = {"exception_type": "AgentTimeoutError"}
    else:
        result["verifier_result"] = {"rewards": {"verification": verification, "reward": verification}}
    return result


class ReportTests(GitTestCase):
    def setUp(self) -> None:
        super().setUp()
        scaffold = committed_copy(SCAFFOLD, self.root / "scaffold")
        # Bare-built trees took two files and 1 + 2 lines; consult-built trees one file and 1 line.
        ignored = (SCAFFOLD / ".gitignore").read_text() + "extra/\n"
        wide = bundle_after(scaffold, self.root / "wide", {".gitignore": ignored, "src/new.ts": "x\ny\n"})
        narrow = bundle_after(scaffold, self.root / "narrow", {"src/new.ts": "x\n"})
        self.job = self.root / "followup-job"
        trials = [
            ("bare-staged-commissions-aa1", 1.0, 3000, 600, wide),
            ("bare-staged-commissions-aa1", 0.0, 5000, 1000, wide),
            ("bare-staged-commissions-bb2", None, 7000, 2690, None),
            ("consult-staged-commissions-cc3", 1.0, 1000, 300, narrow),
            ("consult-staged-commissions-cc3", 1.0, 2000, 500, narrow),
        ]
        for n, (task, verification, tokens, seconds, bundle) in enumerate(trials):
            result = followup_result(task, verification, tokens, seconds)
            write_trial(self.job, f"{task}__{n}", result, bundle, Path())

    def test_each_metric_is_reported_per_source_arm(self):
        summary = followup.summarize(followup.load_arms(self.job))

        self.assertAlmostEqual(summary["passed"]["bare"], 1 / 3)
        self.assertEqual(summary["passed"]["consult"], 1.0)
        self.assertEqual((summary["output_tokens"]["bare"], summary["output_tokens"]["consult"]), (5000, 1500))
        self.assertEqual((summary["agent_seconds"]["bare"], summary["agent_seconds"]["consult"]), (1430, 400))
        self.assertEqual((summary["files_touched"]["bare"], summary["files_touched"]["consult"]), (2, 1))
        self.assertEqual((summary["lines_changed"]["bare"], summary["lines_changed"]["consult"]), (3, 1))

    def test_a_metric_with_spread_in_both_arms_gets_an_interval(self):
        summary = followup.summarize(followup.load_arms(self.job))

        lo, hi = summary["output_tokens"]["interval"]
        self.assertLess(hi, 0.0)
        self.assertLessEqual(lo, summary["output_tokens"]["change"])
        self.assertIsNone(summary["files_touched"]["interval"])

    def test_the_report_names_trials_without_a_reward(self):
        stdout = io.StringIO()
        with redirect_stdout(stdout):
            code = followup.main(["followup.py", "report", str(self.job)])

        self.assertEqual(code, 0)
        text = stdout.getvalue()
        self.assertIn("| pass rate | 33% | 100% | +67% |", text)
        self.assertIn("Trials: 3 on trees built by bare, 2 on trees built by consult.", text)
        self.assertIn("No reward, counted as a fail: bare-staged-commissions-bb2__2", text)


if __name__ == "__main__":
    unittest.main()
