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
from contextlib import redirect_stdout
from pathlib import Path

EVAL_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(EVAL_DIR / "scripts"))

import rule_labels  # noqa: E402


def write_rule_trial(job: Path, task: str, n: int, rules: dict[str, float]) -> Path:
    trial = job / f"{task}__{n}"
    (trial / "verifier").mkdir(parents=True)
    result = {"task_name": f"consult/{task}", "verifier_result": {"rewards": {"reward": 0.8, "verification": 1.0}}}
    (trial / "result.json").write_text(json.dumps(result))
    details = {"rules": {"criteria": [{"name": r, "value": v} for r, v in rules.items()]}}
    (trial / "verifier" / "reward-details.json").write_text(json.dumps(details))
    return trial


class RuleLabelTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def export(self, *jobs: Path) -> list[dict]:
        sheet = self.root / "labels.csv"
        with redirect_stdout(io.StringIO()):
            rule_labels.main(["rule_labels.py", "export", str(sheet), *map(str, jobs)])
        with sheet.open(newline="") as handle:
            return list(csv.DictReader(handle))

    def test_export_writes_one_row_per_rule_verdict_with_the_rule_text_and_trial(self):
        bare = self.root / "bare"
        trial = write_rule_trial(bare, "bug-from-symptom", 0, {"workflow.7": 0.0, "debugging.1": 1.0})
        rows = self.export(bare)
        self.assertEqual([(r["job"], r["rule"], r["automated"]) for r in rows],
                         [("bare", "debugging.1", "1.0"), ("bare", "workflow.7", "0.0")])
        self.assertTrue(rows[1]["rule_text"].startswith("Durable shapes need sign-off before they are built."))
        self.assertEqual(rows[0]["trial_dir"], str(trial))
        self.assertEqual((rows[0]["proposed"], rows[0]["human"]), ("", ""))

    def test_trials_of_tasks_without_rules_are_left_out(self):
        consult = self.root / "consult"
        write_rule_trial(consult, "proof-first-bugfix", 0, {})
        self.assertEqual(self.export(consult), [])

    def write_sheet(self, rows: list[tuple[str, str, str]]) -> Path:
        sheet = self.root / "labelled.csv"
        with sheet.open("w", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=rule_labels.COLUMNS)
            writer.writeheader()
            for rule, automated, human in rows:
                writer.writerow({"rule": rule, "automated": automated, "human": human})
        return sheet

    def test_agreement_counts_labelled_rows_where_check_and_human_match(self):
        sheet = self.write_sheet([("api.1", "1.0", "pass"), ("api.1", "0.0", "fail"), ("api.1", "1.0", "fail"),
                                  ("api.1", "1.0", ""), ("workflow.7", "0.0", "fail")])
        self.assertEqual(rule_labels.agreement(rule_labels.read_sheet(sheet)),
                         {"api.1": (2, 3), "workflow.7": (1, 1)})

    def test_the_agreement_report_gives_each_rules_share(self):
        sheet = self.write_sheet([("api.1", "1.0", "pass"), ("api.1", "1.0", "fail")])
        with redirect_stdout(io.StringIO()) as out:
            rule_labels.main(["rule_labels.py", "agree", str(sheet)])
        self.assertIn("| api.1 | 2 | 1 | 50% |", out.getvalue())

    def test_a_label_other_than_pass_or_fail_stops_the_report(self):
        sheet = self.write_sheet([("api.1", "1.0", "maybe")])
        with self.assertRaisesRegex(SystemExit, "pass or fail"):
            rule_labels.read_sheet(sheet)


if __name__ == "__main__":
    unittest.main()
