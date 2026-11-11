"""Both sides of the forks in fork-cache-or-recompute, fork-queue-or-inline, and fork-retry-or-timeout.

  python3 -m unittest discover eval/verifier/tests

Each task ships two solutions: solution/solve.sh takes the simpler side and
solution/other-side.sh the other. Both must pass the task's hidden check, and
the rule probe must score the oracle 1 and the other side 0. The untouched
workspace fails the hidden check and scores 0, so an idle agent takes neither
side. Scripts run the way consult_lib runs them: passed to
`node --input-type=module -e` with the workspace as the working directory.
Needs Node 22 or later and bash on PATH.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

EVAL_DIR = Path(__file__).resolve().parents[2]
HIDDEN = EVAL_DIR / "verifier" / "hidden"
TASKS = EVAL_DIR / "tasks"


def node(script: Path, workspace: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["node", "--input-type=module", "-e", script.read_text()],
        cwd=workspace,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )


class ForkCase(unittest.TestCase):
    task = ""

    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.workspace = Path(tmp.name) / "app"
        shutil.copytree(TASKS / self.task / "environment" / "workspace", self.workspace)

    @property
    def rule(self) -> str:
        return "fork." + self.task.removeprefix("fork-")

    def apply(self, solution: str) -> None:
        script = TASKS / self.task / "solution" / solution
        subprocess.run(["bash", str(script), str(self.workspace)], check=True, capture_output=True, timeout=60)

    def assertHiddenPasses(self) -> None:
        result = node(HIDDEN / f"{self.task}.mjs", self.workspace)
        self.assertEqual(result.returncode, 0, result.stderr[-1500:])
        visible = subprocess.run(
            ["node", "--test"], cwd=self.workspace, capture_output=True, text=True, timeout=120, check=False
        )
        self.assertEqual(visible.returncode, 0, visible.stdout[-1500:])

    def fork_score(self) -> int:
        result = node(HIDDEN / f"{self.task}.rules.mjs", self.workspace)
        lines = [line for line in result.stdout.splitlines() if line.startswith("{")]
        self.assertTrue(lines, f"probe printed no result: {result.stderr[-1500:]}")
        scores = json.loads(lines[-1])
        self.assertEqual(list(scores), [self.rule])
        return int(scores[self.rule])

    def test_the_rule_is_registered_and_listed(self) -> None:
        meta = json.loads((TASKS / self.task / "tests" / "consult.json").read_text())
        coverage = json.loads((EVAL_DIR / "verifier" / "rules.json").read_text())
        self.assertEqual(meta["rules"], [self.rule])
        self.assertEqual(coverage[self.rule], "check")

    def test_the_simpler_side_passes_and_scores_1(self) -> None:
        self.apply("solve.sh")
        self.assertHiddenPasses()
        self.assertEqual(self.fork_score(), 1)

    def test_the_other_side_passes_and_scores_0(self) -> None:
        self.apply("other-side.sh")
        self.assertHiddenPasses()
        self.assertEqual(self.fork_score(), 0)

    def test_the_untouched_workspace_fails_and_scores_0(self) -> None:
        result = node(HIDDEN / f"{self.task}.mjs", self.workspace)
        self.assertNotEqual(result.returncode, 0, "hidden check passed the starting repository")
        self.assertEqual(self.fork_score(), 0)


class CacheOrRecomputeTests(ForkCase):
    task = "fork-cache-or-recompute"

    def test_the_hidden_check_restores_the_catalog_it_edits(self) -> None:
        catalog = self.workspace / "data" / "catalog.json"
        before = catalog.read_text()
        self.apply("solve.sh")
        self.assertHiddenPasses()
        self.assertEqual(catalog.read_text(), before)


class QueueOrInlineTests(ForkCase):
    task = "fork-queue-or-inline"


class RetryOrTimeoutTests(ForkCase):
    task = "fork-retry-or-timeout"


del ForkCase

if __name__ == "__main__":
    unittest.main()
