"""The release chart: per-task reward, bare against Consult, drawn from a real lift summary.

  python3 -m unittest discover eval/verifier/tests
"""

from __future__ import annotations

import contextlib
import io
import json
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from contextlib import redirect_stdout
from pathlib import Path

EVAL_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(EVAL_DIR / "scripts"))

import charts  # noqa: E402
import lift  # noqa: E402

SVG = "{http://www.w3.org/2000/svg}"
AGENT = "Claude Code"


def write_job(job: Path, rewards: dict[str, list[float]]) -> Path:
    """A Harbor job dir with one trial per reward, in the shape lift.load_trials reads."""
    for task, values in rewards.items():
        for n, value in enumerate(values):
            trial = job / f"{task}__{n}"
            trial.mkdir(parents=True)
            result = {"task_name": f"consult/{task}",
                      "verifier_result": {"rewards": {"reward": value, "verification": 1.0, "judge": 0.5}}}
            (trial / "result.json").write_text(json.dumps(result))
    return job


def luminance(hex_colour: str) -> float:
    channels = [int(hex_colour[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    linear = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def contrast(a: str, b: str) -> float:
    high, low = sorted((luminance(a), luminance(b)), reverse=True)
    return (high + 0.05) / (low + 0.05)


def elements(root: ET.Element, tag: str, css_class: str) -> list[ET.Element]:
    return [e for e in root.iter(f"{SVG}{tag}") if e.get("class") == css_class]


class ChartTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def summary(self, bare: dict[str, list[float]], consult: dict[str, list[float]]) -> dict:
        """lift.summarize output, through the JSON round trip a release file takes."""
        jobs = self.root / f"jobs{len(list(self.root.glob('jobs*')))}"
        result = lift.summarize(lift.load_trials(write_job(jobs / "bare", bare)),
                                lift.load_trials(write_job(jobs / "consult", consult)))
        return json.loads(json.dumps(result))

    def chart(self, summary: dict, theme: dict = charts.LIGHT) -> ET.Element:
        return ET.fromstring(charts.dumbbell_svg(summary, theme, AGENT))

    def three_tasks(self) -> dict:
        return self.summary({"big-lift": [0.3, 0.3], "small-lift": [0.7, 0.7], "loss": [0.8, 0.8]},
                            {"big-lift": [0.9, 0.9], "small-lift": [0.75, 0.75], "loss": [0.6, 0.6]})

    def test_rows_run_from_largest_lift_to_largest_loss(self):
        labels = [t.text for t in elements(self.chart(self.three_tasks()), "text", "task")]
        self.assertEqual(labels, ["big-lift", "small-lift", "loss"])

    def test_each_task_places_its_markers_by_reward(self):
        root = self.chart(self.three_tasks())
        bare, consult = elements(root, "circle", "bare"), elements(root, "circle", "consult")
        self.assertEqual((len(bare), len(consult)), (3, 3))
        self.assertAlmostEqual(float(consult[0].get("cx")) - float(bare[0].get("cx")), 0.6 * charts.PLOT_WIDTH)
        self.assertLess(float(consult[2].get("cx")), float(bare[2].get("cx")))

    def test_a_task_the_bare_job_never_ran_is_left_out_and_named(self):
        summary = self.summary({"kept": [0.4, 0.5]}, {"kept": [0.8, 0.9], "unpaired": [0.9, 0.9]})
        root = self.chart(summary)
        self.assertEqual([t.text for t in elements(root, "text", "task")], ["kept"])
        footer = [t.text for t in elements(root, "text", "footer")]
        self.assertTrue(footer[0].startswith("Suite lift +0.40 across 1 tasks"))
        self.assertIn("Left out, no bare trials (1): unpaired", footer)

    def test_many_left_out_tasks_are_counted_after_the_first_few_names(self):
        consult = {"kept": [0.8], **{f"gone-{i}": [0.9] for i in range(5)}}
        footer = [t.text for t in elements(self.chart(self.summary({"kept": [0.4]}, consult)), "text", "footer")]
        self.assertIn("Left out, no bare trials (5): gone-0, gone-1, gone-2, and 2 more", footer)

    def test_failed_trials_are_counted_only_in_plotted_tasks(self):
        summary = self.summary({"kept": [0.4, 0.5], "both": [0.3, 0.3]}, {"kept": [0.8, 0.9], "unpaired": [0.9]})
        summary["tasks"][0]["failed"] = ["kept__1"]
        summary["tasks"][1]["failed"] = ["unpaired__0", "unpaired__1"]
        footer = [t.text for t in elements(self.chart(summary), "text", "footer")]
        self.assertIn("1 failed trial in the plotted tasks; see the results file", footer)

    def test_a_judge_free_comparison_is_noted(self):
        summary = self.three_tasks()
        summary["judge_excluded"] = True
        footer = [t.text for t in elements(self.chart(summary), "text", "footer")]
        self.assertIn("Rewards exclude the judge: one arm ran without it", footer)

    def test_the_bare_ring_is_drawn_over_the_consult_dot_so_a_tie_shows_both(self):
        circles = [c.get("class") for c in self.chart(self.three_tasks()).iter(f"{SVG}circle")
                   if c.get("class") in ("bare", "consult")]
        self.assertEqual(circles[:2], ["consult", "bare"])

    def test_the_footer_ends_inside_the_canvas_with_room_below(self):
        root = self.chart(self.three_tasks())
        last = float(elements(root, "text", "footer")[-1].get("y"))
        self.assertGreaterEqual(float(root.get("height")) - last, 8)

    def test_main_refuses_an_empty_agent_name(self):
        summary_path = self.root / "summary.json"
        summary_path.write_text(json.dumps(self.three_tasks()))
        with redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(charts.main(["charts.py", str(summary_path), str(self.root / "out"), " "]), 2)

    def test_the_footer_and_description_state_the_suite_lift_and_its_interval(self):
        summary = self.summary({"t": [0.3, 0.35, 0.4]}, {"t": [0.8, 0.85, 0.9]})
        root = self.chart(summary)
        lo, hi = summary["suite"]["reward_interval"]
        footer = elements(root, "text", "footer")[0].text
        self.assertIn(f"90% interval {charts.signed(lo)} to {charts.signed(hi)}", footer)
        self.assertIn(footer, root.find(f"{SVG}desc").text)
        self.assertIn(AGENT, root.find(f"{SVG}title").text)

    def test_one_trial_per_task_says_there_is_no_interval(self):
        footer = elements(self.chart(self.summary({"t": [0.3]}, {"t": [0.8]})), "text", "footer")[0].text
        self.assertIn("no interval", footer)

    def test_the_top_row_names_its_markers_only_when_they_sit_apart(self):
        self.assertEqual([t.text for t in elements(self.chart(self.three_tasks()), "text", "direct-label")],
                         ["Bare", "Consult"])
        close = self.summary({"tie": [0.5]}, {"tie": [0.52]})
        self.assertFalse(elements(self.chart(close), "text", "direct-label"))

    def test_text_meets_aa_contrast_and_markers_three_to_one_in_both_themes(self):
        for theme in (charts.LIGHT, charts.DARK):
            root = self.chart(self.three_tasks(), theme)
            fills = {t.get("fill") for t in root.iter(f"{SVG}text")}
            self.assertFalse(fills & {theme["bare"], theme["consult"]}, "text wears a series colour")
            for fill in fills:
                self.assertGreaterEqual(contrast(fill, theme["surface"]), 4.5, f"{theme['name']} text {fill}")
            for colour in (theme["bare"], theme["consult"]):
                self.assertGreaterEqual(contrast(colour, theme["surface"]), 3.0, f"{theme['name']} marker {colour}")

    def test_the_two_arms_differ_by_shape_not_only_colour(self):
        root = self.chart(self.three_tasks())
        self.assertEqual(elements(root, "circle", "bare")[0].get("fill"), "none")
        self.assertNotEqual(elements(root, "circle", "consult")[0].get("fill"), "none")

    def test_a_task_name_with_markup_characters_is_escaped(self):
        summary = self.three_tasks()
        name = "a<b>&'c\""
        summary["tasks"][0]["task"] = summary["suite"]["tasks"][0] = f"consult/{name}"
        labels = [t.text for t in elements(self.chart(summary), "text", "task")]
        self.assertIn(name, labels)

    def test_every_eval_task_name_and_extreme_reward_fits_the_canvas(self):
        names = sorted(p.name for p in (EVAL_DIR / "tasks").iterdir() if (p / "task.toml").is_file())
        bare = {n: [float(i % 2)] for i, n in enumerate(names)}
        consult = {n: [1.0 - float(i % 2)] for i, n in enumerate(names)}
        root = self.chart(self.summary(bare, consult))
        width = float(root.get("width"))
        for label in elements(root, "text", "task"):
            self.assertGreaterEqual(float(label.get("x")) - charts.label_width(label.text), 0.0, label.text)
        for circle in root.iter(f"{SVG}circle"):
            cx, r = float(circle.get("cx")), float(circle.get("r"))
            self.assertTrue(0.0 <= cx - r and cx + r <= width, circle.attrib)

    def test_a_summary_it_cannot_draw_stops(self):
        with self.assertRaisesRegex(SystemExit, "no task that both arms ran"):
            disjoint = self.summary({"api-error-contract": [0.5]}, {"proof-first-bugfix": [0.5]})
            charts.dumbbell_svg(disjoint, charts.LIGHT, AGENT)
        summary = self.three_tasks()
        summary["tasks"][0]["consult"] = 1.2
        with self.assertRaisesRegex(SystemExit, "outside 0 to 1"):
            charts.dumbbell_svg(summary, charts.LIGHT, AGENT)

    def test_a_tiny_negative_lift_prints_as_zero(self):
        self.assertEqual(charts.signed(-0.001), "+0.00")

    def test_main_writes_a_light_and_a_dark_chart_named_for_the_agent(self):
        summary_path, out = self.root / "summary.json", self.root / "charts"
        summary_path.write_text(json.dumps(self.three_tasks()))
        with redirect_stdout(io.StringIO()):
            charts.main(["charts.py", str(summary_path), str(out), AGENT])
        for theme in ("light", "dark"):
            ET.fromstring((out / f"release-lift-claude-code-{theme}.svg").read_text())


if __name__ == "__main__":
    unittest.main()
