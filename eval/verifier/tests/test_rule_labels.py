"""The rule calibration sheet: exporting rule verdicts to label, and agreement once labelled.

  python3 -m unittest discover eval/verifier/tests
"""

from __future__ import annotations

import csv
import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

EVAL_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(EVAL_DIR / "scripts"))

import rule_labels  # noqa: E402


def write_rule_trial(job: Path, task: str, n: int, rules: dict[str, float], steps: tuple[str, ...] = ()) -> Path:
    """A trial whose final step scored these rule criteria; an empty dict is lift's no_rules placeholder."""
    trial = job / f"{task}__{n}"
    final = trial / "steps" / steps[-1] if steps else trial
    (final / "verifier").mkdir(parents=True)
    result = {"task_name": f"consult/{task}", "verifier_result": {"rewards": {"reward": 0.8, "verification": 1.0}}}
    if steps:
        result["step_results"] = [{"step_name": s} for s in steps]
    (trial / "result.json").write_text(json.dumps(result))
    criteria = [{"name": r, "value": v} for r, v in rules.items()] or [{"name": "no_rules", "value": 1.0}]
    (final / "verifier" / "reward-details.json").write_text(json.dumps({"rules": {"criteria": criteria}}))
    return trial


class ExportTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def export(self, *jobs: Path) -> list[dict]:
        sheet = self.root / "labels.csv"
        with redirect_stdout(io.StringIO()):
            self.assertEqual(rule_labels.main(["rule_labels.py", "export", str(sheet), *map(str, jobs)]), 0)
        with sheet.open(newline="") as handle:
            return list(csv.DictReader(handle))

    def test_export_writes_one_row_per_rule_verdict_with_the_rule_text_and_evidence(self):
        trial = write_rule_trial(self.root / "bare", "bug-from-symptom", 0, {"workflow.7": 0.0, "debugging.1": 1.0})
        rows = self.export(self.root / "bare")
        self.assertEqual([(r["job"], r["rule"], r["automated"]) for r in rows],
                         [("bare", "debugging.1", "1.0"), ("bare", "workflow.7", "0.0")])
        self.assertTrue(rows[1]["rule_text"].startswith("Durable shapes need sign-off before they are built."))
        self.assertEqual(rows[0]["evidence_dir"], str(trial.resolve()))
        self.assertEqual((rows[0]["proposed"], rows[0]["human"]), ("", ""))

    def test_a_rule_text_leaves_out_the_tables_inside_the_rule(self):
        """workflow.7 holds the sign-off table; a reviewer needs the rule, not the table rows."""
        self.assertNotIn("|", rule_labels.rule_text("workflow.7"))
        self.assertIn("no human can answer", rule_labels.rule_text("workflow.7"))

    def test_a_multi_step_trial_points_at_its_final_steps_evidence(self):
        trial = write_rule_trial(self.root / "consult", "money-field-change", 0, {"api.1": 1.0}, ("brief", "build"))
        self.assertEqual(self.export(self.root / "consult")[0]["evidence_dir"], str((trial / "steps" / "build").resolve()))

    def test_sign_off_rules_and_tasks_without_rules_are_left_out(self):
        """Sign-off rules never score in the rules dimension, so their rows cannot inform its weight."""
        write_rule_trial(self.root / "consult", "proof-first-bugfix", 0, {})
        write_rule_trial(self.root / "consult", "service-from-brief", 0, {"scaffolding.1": 1.0, "api.1": 0.0})
        self.assertEqual([r["rule"] for r in self.export(self.root / "consult")], ["api.1"])

    def test_export_reads_every_job_given(self):
        write_rule_trial(self.root / "bare", "bug-from-symptom", 0, {"debugging.1": 0.0})
        write_rule_trial(self.root / "consult", "bug-from-symptom", 0, {"debugging.1": 1.0})
        self.assertEqual([r["job"] for r in self.export(self.root / "bare", self.root / "consult")], ["bare", "consult"])

    def test_export_refuses_to_overwrite_a_sheet(self):
        write_rule_trial(self.root / "bare", "bug-from-symptom", 0, {"debugging.1": 0.0})
        sheet = self.root / "labels.csv"
        sheet.write_text("job,human\nbare,pass\n")
        with redirect_stderr(io.StringIO()) as err:
            self.assertEqual(rule_labels.main(["rule_labels.py", "export", str(sheet), str(self.root / "bare")]), 2)
        self.assertIn("may hold labels", err.getvalue())
        self.assertEqual(sheet.read_text(), "job,human\nbare,pass\n")

    def test_export_from_a_job_without_trials_stops(self):
        with redirect_stderr(io.StringIO()) as err:
            code = rule_labels.main(["rule_labels.py", "export", str(self.root / "s.csv"), str(self.root / "typo")])
        self.assertEqual(code, 2)
        self.assertIn("no trials in", err.getvalue())
        self.assertFalse((self.root / "s.csv").exists())


class AgreementTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def sheet(self, rows: list[tuple[str, str, str]]) -> Path:
        sheet = self.root / "labelled.csv"
        with sheet.open("w", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=rule_labels.COLUMNS)
            writer.writeheader()
            for rule, automated, human in rows:
                writer.writerow({"trial": "t__0", "rule": rule, "automated": automated, "human": human})
        return sheet

    def test_agreement_counts_matches_false_passes_and_false_fails(self):
        rows = rule_labels.read_sheet(self.sheet([("api.1", "1.0", "pass"), ("api.1", "0.0", "fail"),
                                                  ("api.1", "1.0", "fail"), ("api.1", "0.0", "Pass"),
                                                  ("api.1", "1.0", ""), ("workflow.7", "0.0", "fail")]))
        result = rule_labels.agreement(rows)
        self.assertEqual(result["api.1"], {"labelled": 4, "agree": 2, "false_pass": 1, "false_fail": 1})
        self.assertEqual(result["workflow.7"]["agree"], 1)

    def test_a_score_of_one_half_counts_as_a_pass(self):
        rows = rule_labels.read_sheet(self.sheet([("api.1", "0.5", "pass")]))
        self.assertEqual(rule_labels.agreement(rows)["api.1"]["agree"], 1)

    def test_the_agreement_report_gives_each_rules_counts_and_share(self):
        sheet = self.sheet([("api.1", "1.0", "pass"), ("api.1", "1.0", "fail")])
        with redirect_stdout(io.StringIO()) as out:
            rule_labels.main(["rule_labels.py", "agree", str(sheet)])
        self.assertIn("| api.1 | 2 | 1 | 1 | 0 | 50% |", out.getvalue())

    def test_an_unreadable_label_or_score_stops_the_report_naming_its_row(self):
        with self.assertRaisesRegex(SystemExit, r"row 2 \(t__0, api.1\): human must be pass or fail"):
            rule_labels.read_sheet(self.sheet([("api.1", "1.0", "maybe")]))
        with self.assertRaisesRegex(SystemExit, "row 2 .*automated must be a number"):
            rule_labels.read_sheet(self.sheet([("api.1", "", "pass")]))


if __name__ == "__main__":
    unittest.main()
