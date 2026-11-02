"""The judge calibration sheet: blind export, judge-human agreement, and repeat agreement.

  python3 -m unittest discover eval/verifier/tests

Fixture jobs hold rejudged trials of a real task (bug-from-symptom), so the
export reads that task's resolved rubric as the judges did.
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

import judge_labels as jl

TASK = "bug-from-symptom"
ITEMS = [
    item for item in json.loads((EVAL_DIR / "tasks" / TASK / "tests" / "rubric" / "items.json").read_text())["items"]
]
# The bundle and the agent's reply mention Consult, which the labeller must not see.
BUNDLE = "# Changes\n\nPer the consult:proof skill, src/snapshot.js now deep-copies.\n\n## Final agent message\n\nDone."


def answer(item: dict, value: str) -> dict:
    return {
        **{k: item[k] for k in ("id", "dimension", "tier", "polarity", "rules")},
        "answer": value,
        "source": "judge",
        "evidence": f"src/snapshot.js:4 for {item['id']}",
        "why": f"reason {value}",
    }


def write_trial(job: Path, name: str, answers: list[dict]) -> None:
    trial = job / name
    (trial / "verifier").mkdir(parents=True)
    (trial / "agent").mkdir()
    (trial / "result.json").write_text(json.dumps({"task_name": f"consult/{TASK}"}))
    (trial / "agent" / "trajectory.json").write_text(json.dumps({"steps": []}))
    (trial / "verifier" / "judge-bundle.md").write_text(BUNDLE)
    (trial / "verifier" / "judge-items.json").write_text(json.dumps({"items": answers}))


class LabelTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        self.bare = self.root / "2026-11-02-rules-claude-code-bare-rejudged"
        self.consult = self.root / "2026-11-02-rules-claude-code-consult-rejudged"
        # Bare: the judge says yes to everything. Consult: no to the first item, unknown to the second.
        for n in range(2):
            write_trial(self.bare, f"{TASK}__b{n}", [answer(i, "yes") for i in ITEMS])
            consult = [answer(i, "no" if k == 0 else "unknown" if k == 1 else "yes") for k, i in enumerate(ITEMS)]
            write_trial(self.consult, f"{TASK}__c{n}", consult)
        self.sheet = self.root / "labels.csv"

    def export(self, *extra: str) -> int:
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            return jl.main(["judge_labels.py", "export", str(self.sheet), str(self.bare), str(self.consult), *extra])

    def rows(self) -> list[dict]:
        with self.sheet.open(newline="") as handle:
            return list(csv.DictReader(handle))

    def label(self, choose) -> None:
        """Write the human column with choose(row, key entry) for every row."""
        key = json.loads(jl.key_path(self.sheet).read_text())["rows"]
        rows = self.rows()
        for row in rows:
            row["human"] = choose(row, key[row["row"]])
        with self.sheet.open("w", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=jl.COLUMNS)
            writer.writeheader()
            writer.writerows(rows)


class ExportTests(LabelTestCase):
    def test_the_sheet_hides_the_answer_the_reason_and_the_arm(self):
        self.assertEqual(self.export(), 0)
        sheet = self.sheet.read_text()
        self.assertNotIn("answer", self.rows()[0])
        self.assertNotIn("reason ", sheet)
        self.assertNotIn("src/snapshot.js:4 for", sheet)
        self.assertNotIn("bare", sheet)
        self.assertNotIn("consult", sheet.lower())

    def test_each_case_file_holds_the_request_and_the_change_with_consult_scrubbed(self):
        self.export()
        cases = sorted(jl.cases_dir(self.sheet).glob("*.md"))
        self.assertEqual(len(cases), 4)
        text = cases[0].read_text()
        self.assertIn("src/snapshot.js now deep-copies", text)
        self.assertIn("## Request", text)
        self.assertNotIn("consult:", text)

    def test_the_key_keeps_what_the_sheet_hides(self):
        self.export()
        key = json.loads(jl.key_path(self.sheet).read_text())
        entry = next(iter(key["rows"].values()))
        self.assertEqual(set(entry), {"job", "trial", "arm", "answer", "evidence", "why"})
        self.assertEqual(sum(t["unknown"] for t in key["totals"].values()), 2)

    def test_each_dimension_samples_half_from_each_arm(self):
        self.export("--per-dimension", "4")
        key = json.loads(jl.key_path(self.sheet).read_text())["rows"]
        for dimension in {r["dimension"] for r in self.rows()}:
            arms = [key[r["row"]]["arm"] for r in self.rows() if r["dimension"] == dimension]
            self.assertEqual(arms.count("bare"), arms.count("consult"), dimension)

    def test_the_same_seed_gives_the_same_sheet(self):
        self.export("--seed", "7")
        first = self.sheet.read_text()
        for path in (self.sheet, jl.key_path(self.sheet)):
            path.unlink()
        for case in jl.cases_dir(self.sheet).iterdir():
            case.unlink()
        jl.cases_dir(self.sheet).rmdir()
        self.export("--seed", "7")
        self.assertEqual(self.sheet.read_text(), first)

    def test_a_trial_rescore_flagged_is_left_out(self):
        result = self.consult / f"{TASK}__c0" / "result.json"
        result.write_text(json.dumps({"task_name": f"consult/{TASK}", "rescore": {"flags": ["not the one judged"]}}))
        self.export()
        key = json.loads(jl.key_path(self.sheet).read_text())
        self.assertNotIn(f"{TASK}__c0", {e["trial"] for e in key["rows"].values()})
        self.assertEqual(sum(t["unknown"] for t in key["totals"].values()), 1)

    def test_items_a_failed_call_left_unknown_count_toward_the_unknown_rate(self):
        failed = [{**answer(i, "unknown"), "source": "missing", "evidence": ""} for i in ITEMS]
        write_trial(self.bare, f"{TASK}__failed", failed)
        self.export()
        key = json.loads(jl.key_path(self.sheet).read_text())
        self.assertEqual(sum(t["unknown"] for t in key["totals"].values()), 2 + len(ITEMS))
        self.assertNotIn(f"{TASK}__failed", {e["trial"] for e in key["rows"].values()})

    def test_export_refuses_to_overwrite_a_sheet_that_may_hold_labels(self):
        self.export()
        self.assertEqual(self.export(), 2)

    def test_a_job_whose_name_hides_its_arm_is_refused(self):
        with self.assertRaises(SystemExit):
            jl.job_arm(Path("runs/2026-11-02-rules-claude-code-rejudged"))

    def test_round_robin_spreads_the_sample_across_tasks(self):
        pool = [{"task": "a"}] * 5 + [{"task": "b"}] * 5
        self.assertEqual([p["task"] for p in jl.round_robin(pool, 4)], ["a", "b", "a", "b"])


class AgreeTests(LabelTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.export()

    def test_a_human_who_agrees_with_every_answer_passes_kappa_and_bias(self):
        self.label(lambda row, key: key["answer"] if key["answer"] in jl.LABELS else "yes")
        # The consult trials' no answers to the first item make kappa defined in its dimension.
        first = jl.agreement(self.sheet)[ITEMS[0]["dimension"]]
        self.assertEqual((first["kappa"], first["bias"]), (1.0, {"bare": 0.0, "consult": 0.0}))

    def test_a_judge_too_generous_to_one_arm_shows_as_bias(self):
        self.label(
            lambda row, key: "no" if key["arm"] == "bare" else key["answer"] if key["answer"] in jl.LABELS else "yes"
        )
        result = jl.agreement(self.sheet)
        bare_bias = [r["bias"]["bare"] for r in result.values() if r["bias"]["bare"] is not None]
        self.assertTrue(bare_bias)
        self.assertTrue(all(b == 1.0 for b in bare_bias))
        self.assertFalse(any(r["passes"] for r in result.values()))

    def test_unlabelled_rows_are_left_out(self):
        result = jl.agreement(self.sheet)
        self.assertTrue(all(r["labelled"] == 0 and r["kappa"] is None for r in result.values()))

    def test_a_sheet_saved_with_a_byte_order_mark_still_reads(self):
        self.label(lambda row, key: "yes")
        self.sheet.write_bytes(b"\xef\xbb\xbf" + self.sheet.read_bytes())
        self.assertTrue(all(r["human"] == "yes" for r in jl.read_labels(self.sheet)))

    def test_a_label_other_than_yes_or_no_is_refused(self):
        self.label(lambda row, key: "maybe")
        with self.assertRaises(SystemExit):
            jl.read_labels(self.sheet)

    def test_the_unknown_rate_counts_every_judge_answer_in_the_jobs(self):
        result = jl.agreement(self.sheet)
        dimension = ITEMS[1]["dimension"]
        total = sum(1 for i in ITEMS if i["dimension"] == dimension) * 4
        self.assertAlmostEqual(result[dimension]["unknown"], 2 / total)

    def test_the_table_names_the_gate(self):
        self.assertIn("Gate: kappa >= 0.7", jl.render_agreement(jl.agreement(self.sheet)))


class KappaTests(unittest.TestCase):
    def test_kappa_matches_a_worked_example(self):
        # 20 yes-yes, 5 yes-no, 10 no-yes, 15 no-no: observed 0.7, chance 0.5, kappa 0.4.
        pairs = [("yes", "yes")] * 20 + [("yes", "no")] * 5 + [("no", "yes")] * 10 + [("no", "no")] * 15
        self.assertAlmostEqual(jl.kappa(pairs), 0.4)

    def test_kappa_is_undefined_when_both_raters_always_say_yes(self):
        self.assertIsNone(jl.kappa([("yes", "yes")] * 3))


class RepeatTests(LabelTestCase):
    def test_repeat_agreement_counts_matching_answers_per_dimension(self):
        second = self.root / "2026-11-02-rules-claude-code-bare-rejudged-repeat"
        flipped = [answer(i, "no" if k == 0 else "yes") for k, i in enumerate(ITEMS)]
        for n in range(2):
            write_trial(second, f"{TASK}__b{n}", flipped)
        result = jl.repeat_agreement([(self.bare, second)])
        dimension = ITEMS[0]["dimension"]
        per_trial = sum(1 for i in ITEMS if i["dimension"] == dimension)
        self.assertEqual(result[dimension], {"compared": 2 * per_trial, "same": 2 * (per_trial - 1)})

    def test_repeat_needs_pairs(self):
        with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            jl.main(["judge_labels.py", "repeat", str(self.bare)])


if __name__ == "__main__":
    unittest.main()
