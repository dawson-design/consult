"""Judge rubrics: templates quote their rules, and a bad task rubric stops the sync.

python3 -m unittest discover eval/verifier/tests
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

EVAL_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(EVAL_DIR / "scripts"))
sys.path.insert(0, str(EVAL_DIR / "verifier" / "shared"))

import rubric
import sync_tests
from rule_labels import rule_text

COVERAGE = json.loads(rubric.RULES_PATH.read_text())
TEMPLATES = rubric.load_templates()
FILLS = {
    "calculation": "`prorate(plan, from, to)` in `src/billing/prorate.ts`",
    "state": "the refund status",
    "state_location": "`src/refunds/types.ts`",
    "expected_surface": "`PORT` and `DATABASE_URL`",
    "requested_behavior": "partial refunds",
    "input": "the refund request body",
    "entry_point": "`POST /refunds`",
    "check": "the ownership check",
    "rule": "the refund cap",
    "bug": "the duplicated invoice",
}


def filled(template_id: str, **overrides: str) -> dict:
    """A task item that extends the template and fills its placeholders from FILLS."""
    template = TEMPLATES[template_id]
    item = {"id": f"task.{template_id.split('.')[1]}", "extends": template_id}
    for field in ("question", "look_at", "yes_when", "no_when"):
        if "{" in template[field]:
            item[field] = template[field].format(**FILLS)
    item.update(overrides)
    return item


def valid_items() -> list[dict]:
    """Twelve items over all five dimensions, with at least one must-have."""
    return [filled(template_id) for template_id in list(TEMPLATES)[:12]]


def problems_for(items: list[dict]) -> list[str]:
    resolved, problems = rubric.resolve_rubric({"items": items}, TEMPLATES)
    return problems + rubric.rubric_problems(resolved, COVERAGE, rule_text)


class TemplateTests(unittest.TestCase):
    def test_every_template_quotes_its_rule_verbatim(self) -> None:
        self.assertEqual(rubric.template_problems(TEMPLATES, COVERAGE, rule_text), [])

    def test_templates_cover_every_dimension(self) -> None:
        self.assertEqual({t["dimension"] for t in TEMPLATES.values()}, set(rubric.DIMENSIONS))


class RubricValidationTests(unittest.TestCase):
    def test_valid_rubric_has_no_problems_and_resolves_template_fields(self) -> None:
        items = valid_items()
        self.assertEqual(problems_for(items), [])
        resolved, _ = rubric.resolve_rubric({"items": items}, TEMPLATES)
        first = resolved[0]
        self.assertEqual(first["extends"], items[0]["extends"])
        self.assertEqual(first["rules"], TEMPLATES[items[0]["extends"]]["rules"])
        self.assertNotIn("{", first["question"])

    def test_fabricated_key_phrase_fails(self) -> None:
        items = valid_items()
        items[0]["key_phrase"] = "Always prefer clever code."
        self.assertTrue(any("key_phrase is not verbatim" in p for p in problems_for(items)))

    def test_unknown_rule_id_fails(self) -> None:
        items = valid_items()
        items[0]["rules"] = ["core.99"]
        self.assertTrue(any("unknown rule ids core.99" in p for p in problems_for(items)))

    def test_unknown_template_fails(self) -> None:
        items = valid_items()
        items[0]["extends"] = "scope.not_a_template"
        self.assertTrue(any("extends unknown template" in p for p in problems_for(items)))

    def test_unfilled_placeholder_fails(self) -> None:
        items = valid_items()
        del items[0]["question"]
        self.assertTrue(any("placeholders in question" in p for p in problems_for(items)))

    def test_negative_item_must_ask_does_not(self) -> None:
        items = valid_items()
        negative = next(i for i, item in enumerate(items) if TEMPLATES[item["extends"]]["polarity"] == "negative")
        items[negative]["question"] = "Is the change free of new options?"
        self.assertTrue(any("negative item's question" in p for p in problems_for(items)))

    def test_positive_item_must_not_ask_does_not(self) -> None:
        items = valid_items()
        items[0]["question"] = "Does NOT read the clock?"
        self.assertTrue(any("negative item's question" in p for p in problems_for(items)))

    def test_size_bounds(self) -> None:
        self.assertTrue(any("a rubric holds" in p for p in problems_for(valid_items()[:11])))
        many = [filled(template_id, id=f"task.n{i}") for i, template_id in enumerate(list(TEMPLATES)[:21])]
        self.assertTrue(any("a rubric holds" in p for p in problems_for(many)))

    def test_a_readout_rubric_holds_one_to_six_items(self) -> None:
        resolved, _ = rubric.resolve_rubric({"items": valid_items()[:2]}, TEMPLATES)
        self.assertEqual(rubric.rubric_problems(resolved, COVERAGE, rule_text, readout=True), [])
        self.assertTrue(any("a rubric holds" in p for p in rubric.rubric_problems(resolved, COVERAGE, rule_text)))
        resolved, _ = rubric.resolve_rubric({"items": valid_items()[:7]}, TEMPLATES)
        found = rubric.rubric_problems(resolved, COVERAGE, rule_text, readout=True)
        self.assertTrue(any("a readout rubric holds" in p for p in found))

    def test_duplicate_ids_fail(self) -> None:
        items = valid_items()
        items[1]["id"] = items[0]["id"]
        self.assertTrue(any("duplicate item ids" in p for p in problems_for(items)))

    def test_needs_a_must_have_item(self) -> None:
        items = [dict(item, tier="quality") for item in valid_items()]
        self.assertTrue(any("at least one must-have" in p for p in problems_for(items)))

    def test_bad_enum_values_fail(self) -> None:
        items = valid_items()
        items[0].update(dimension="vibes", tier="nice", polarity="maybe")
        found = " ".join(problems_for(items))
        for word in ("dimension must be", "tier must be", "polarity must be"):
            self.assertIn(word, found)


class SyncTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.rubrics = Path(self._tmp.name)
        (self.rubrics / "core_items.json").write_text(rubric.TEMPLATES_PATH.read_text())
        self.task = next(t for t in sync_tests.task_dirs() if sync_tests.task_kind(t) == "code")

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def copies(self, task: Path | None = None, kind: str = "code") -> list[tuple[bytes, Path]]:
        with (
            mock.patch.object(rubric, "RUBRICS_DIR", self.rubrics),
            mock.patch.object(rubric, "TEMPLATES_PATH", self.rubrics / "core_items.json"),
        ):
            return sync_tests.rubric_copies(task or self.task, kind)

    def test_task_without_rubric_gets_no_items_file(self) -> None:
        self.assertEqual(self.copies(), [])

    def test_valid_rubric_writes_resolved_items(self) -> None:
        (self.rubrics / f"{self.task.name}.json").write_text(json.dumps({"items": valid_items()}))
        [(content, dest)] = self.copies()
        self.assertEqual(dest, self.task / "tests" / "rubric" / "items.json")
        items = json.loads(content)["items"]
        self.assertEqual(len(items), 12)
        self.assertTrue(all(set(rubric.FIELDS) <= set(item) for item in items))

    def test_a_readout_rubric_gives_the_rubric_no_weight(self) -> None:
        (self.rubrics / f"{self.task.name}.json").write_text(json.dumps({"readout": True, "items": valid_items()[:2]}))
        with mock.patch.object(rubric, "RUBRICS_DIR", self.rubrics):
            weights = sync_tests.reward_toml(self.task, "code").decode()
        self.assertRegex(weights, r"\brubric = 0\.0\b")
        self.assertNotRegex(sync_tests.reward_toml(self.task, "code").decode(), r"\brubric = 0\.0\b")

    def test_invalid_rubric_stops_the_sync(self) -> None:
        items = valid_items()
        items[0]["key_phrase"] = "made up"
        (self.rubrics / f"{self.task.name}.json").write_text(json.dumps({"items": items}))
        with self.assertRaises(SystemExit) as raised:
            self.copies()
        self.assertIn("rubric problems", str(raised.exception))

    def test_a_routing_task_cannot_have_a_rubric(self):
        routing = next(t for t in sync_tests.task_dirs() if sync_tests.task_kind(t) == "routing")
        (self.rubrics / f"{routing.name}.json").write_text(json.dumps({"items": valid_items()}))
        with self.assertRaises(SystemExit) as raised:
            self.copies(routing, "routing")
        self.assertIn("only code tasks have rubrics", str(raised.exception))


class RubricEdgeCaseTests(unittest.TestCase):
    def test_key_phrase_ignores_whitespace_and_bold(self) -> None:
        items = valid_items()
        phrase = TEMPLATES[items[0]["extends"]]["key_phrase"]
        items[0]["key_phrase"] = "**" + phrase.replace(" ", "\n   ", 2) + "**"
        self.assertEqual(problems_for(items), [])

    def test_key_phrase_may_come_from_the_second_rule(self) -> None:
        items = valid_items()
        items[0]["rules"] = ["core.2", "default.5"]
        items[0]["key_phrase"] = "represent states as explicit variants"
        self.assertEqual(problems_for(items), [])

    def test_unknown_key_fails(self) -> None:
        items = valid_items()
        items[0]["questoin"] = "typo"
        self.assertTrue(any("unknown keys questoin" in p for p in problems_for(items)))

    def test_literal_code_braces_are_not_placeholders(self) -> None:
        items = valid_items()
        items[0]["question"] = "Does `prorate` return `{ ok: true }` without reading the clock?"
        self.assertEqual(problems_for(items), [])

    def test_non_string_field_fails_without_crashing(self) -> None:
        items = valid_items()
        items[0]["question"] = 42
        self.assertTrue(any("every other field a string" in p for p in problems_for(items)))


class StalePathsTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.task = self.root / "some-task"
        self.rubrics = self.root / "rubrics"
        self.rubrics.mkdir()

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def stale(self, kind: str) -> list[Path]:
        with mock.patch.object(rubric, "RUBRICS_DIR", self.rubrics):
            return sync_tests.stale_paths(self.task, kind)

    def write(self, rel: str) -> Path:
        path = self.task / "tests" / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{}")
        return path

    def test_items_file_without_rubric_is_stale(self):
        items = self.write("rubric/items.json")
        self.assertEqual(self.stale("code"), [items])
        (self.rubrics / "some-task.json").write_text("{}")
        self.assertEqual(self.stale("code"), [])

    def test_a_code_task_drops_the_generic_judge_it_used_to_have(self):
        self.write("judge/quality.toml")
        self.assertEqual(self.stale("code"), [self.task / "tests" / "judge"])

    def test_a_routing_task_keeps_its_judge(self):
        self.write("judge/quality.toml")
        self.assertEqual(self.stale("routing"), [])


if __name__ == "__main__":
    unittest.main()
