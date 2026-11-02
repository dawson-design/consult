"""The oracle judge check: which tasks it can check, what it asks the judges, and what fails the gate.

No test builds an image or calls a judge.

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

import oracle_judge as oj


def item(item_id: str, dimension: str, tier: str = "must") -> dict:
    return {"id": item_id, "dimension": dimension, "tier": tier}


ITEMS = [
    item("structure.a", "structure"),
    item("scope.a", "scope"),
    item("scope.b", "scope", "quality"),
    item("report.a", "report"),
]


def answer(item_id: str, answer: str, tier: str = "must") -> dict:
    return {"id": item_id, "tier": tier, "answer": answer, "evidence": "src/a.js:1", "why": "w"}


class TaskSelectionTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.tasks = Path(self._tmp.name)
        for task, rubric, oracle in (("ready", True, True), ("no-oracle", True, False), ("no-rubric", False, True)):
            tests = self.tasks / task / "tests" / "rubric"
            tests.mkdir(parents=True)
            if rubric:
                (tests / "items.json").write_text(json.dumps({"items": ITEMS}))
            if oracle:
                (self.tasks / task / "solution").mkdir()
                (self.tasks / task / "solution" / "solve.sh").write_text("exit 0\n")
        patcher = mock.patch.object(oj, "TASKS_DIR", self.tasks)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(self._tmp.cleanup)

    def test_only_tasks_with_a_rubric_and_an_oracle_are_checked(self):
        tasks, problems = oj.oracle_tasks(None)
        self.assertEqual(tasks, ["ready"])
        self.assertEqual(problems, ["no-oracle: no oracle (solution/solve.sh)"])

    def test_a_named_task_without_a_rubric_is_reported(self):
        tasks, problems = oj.oracle_tasks(["no-rubric", "ready"])
        self.assertEqual(tasks, ["ready"])
        self.assertIn("no-rubric: no rubric", problems[0])

    def test_without_a_mode_it_prints_the_call_count_and_runs_nothing(self):
        out = io.StringIO()
        with redirect_stdout(out), mock.patch.object(oj, "check_task") as check:
            self.assertEqual(oj.main(["oracle_judge.py", "--tasks", "ready"]), 0)
        check.assert_not_called()
        self.assertIn("1 tasks, 2 judge calls (up to 4 with retries)", out.getvalue())

    def test_running_the_judges_needs_the_subscription_token(self):
        with (
            mock.patch.dict("os.environ", {}, clear=True),
            redirect_stdout(io.StringIO()),
            mock.patch.object(oj, "check_task") as check,
            mock.patch.object(sys, "stderr", io.StringIO()),
        ):
            self.assertEqual(oj.main(["oracle_judge.py", "--tasks", "ready", "--yes"]), 2)
        check.assert_not_called()


class OracleTrajectoryTests(unittest.TestCase):
    def test_a_multi_step_oracle_replies_with_its_proposal(self):
        trajectory = oj.oracle_trajectory("money-field-change")["steps"]
        self.assertEqual([s["source"] for s in trajectory], ["user", "agent"] * 3)
        self.assertTrue(trajectory[0]["message"].startswith("# Multi-Currency Orders"))
        self.assertIn("totalMoney", trajectory[1]["message"])
        self.assertEqual(trajectory[3]["message"], "")

    def test_the_runner_finds_the_proposal_as_the_reply_the_approval_answered(self):
        sys.path.insert(0, str(EVAL_DIR / "verifier" / "shared"))
        import judge_runner

        instruction = (oj.TASKS_DIR / "money-field-change" / "tests" / "rubric" / "instruction.md").read_text()
        steps = oj.oracle_trajectory("money-field-change")["steps"]
        replies = judge_runner.earlier_replies(instruction, steps)
        self.assertIn("brief turn", replies[0][0])
        self.assertIn("totalMoney", replies[0][1])

    def test_a_single_step_task_has_no_conversation(self):
        self.assertEqual(oj.oracle_trajectory("api-error-contract"), {"steps": []})


class GateTests(unittest.TestCase):
    def test_the_report_dimension_is_left_out(self):
        self.assertEqual([i["id"] for i in oj.code_items(ITEMS)], ["structure.a", "scope.a", "scope.b"])
        self.assertEqual(oj.judge_calls(ITEMS), 2)

    def test_a_must_item_fails_unless_it_answers_yes(self):
        result = {
            "items": [
                answer("structure.a", "yes"),
                answer("scope.a", "unknown"),
                answer("scope.c", "no"),
                answer("scope.b", "no", "quality"),
            ]
        }
        self.assertEqual([r["id"] for r in oj.gate(result)], ["scope.a", "scope.c"])

    def test_failed_calls_and_missed_items_reach_the_summary(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "judge-items.json"
            result = {
                "unknown": 1,
                "calls": [{"dimension": "scope", "error": "the call timed out after 900s"}],
                "items": [answer("scope.a", "unknown")],
            }
            path.write_text(json.dumps(result))
            row = {"task": "t", "oracle": "pass", "failed_must": None, "errors": []}
            oj.judged(row, path)
        self.assertEqual(row["errors"], ["scope judge: the call timed out after 900s"])
        self.assertEqual([i["id"] for i in row["failed_must"]], ["scope.a"])
        summary = oj.render([row], judged_run=True)
        self.assertIn("| t | pass | 1 | 1 |", summary)
        self.assertIn("`scope.a`: unknown", summary)


if __name__ == "__main__":
    unittest.main()
