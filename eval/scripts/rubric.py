"""Load, resolve, and validate the per-task judge rubrics.

A rubric is the checklist the code judges answer for one task: 12 to 20
atomic yes/no items, each tied to the Consult rules it applies. A readout
rubric (`"readout": true`) holds 1 to 6 items that score rules lift.py reports
but the task reward leaves out: sync_tests.py zeroes its rubric weight. The task
author writes it in eval/verifier/rubrics/<task>.json. An item either spells
out every field or names a shared template from
eval/verifier/rubrics/core_items.json with `extends` and overrides the
task-specific fields. sync_tests.py resolves each rubric against the
templates, validates it here, and writes the result to the task's
tests/judge/items.json, which the judge runner reads.

"yes" always means the item is met. A negative item ("Does NOT ...") is
phrased so that yes is the good answer, which keeps the met rate one number.

Validation returns a list of problems instead of raising, so callers decide
how to fail. Standard library only, so CI's bare python3 runs it.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

EVAL_DIR = Path(__file__).resolve().parent.parent
RUBRICS_DIR = EVAL_DIR / "verifier" / "rubrics"
TEMPLATES_PATH = RUBRICS_DIR / "core_items.json"
RULES_PATH = EVAL_DIR / "verifier" / "rules.json"

DIMENSIONS = ("structure", "scope", "boundaries", "proof", "report")
POLARITIES = ("positive", "negative")
TIERS = ("must", "quality")
FIELDS = ("id", "dimension", "rules", "key_phrase", "question", "polarity", "tier", "look_at", "yes_when", "no_when")
MIN_ITEMS = 12
MAX_ITEMS = 20
READOUT_ITEMS = (1, 6)
ITEM_ID_RE = re.compile(r"^[a-z][a-z0-9_]*(\.[a-z0-9_]+)+$")
PLACEHOLDER_RE = re.compile(r"\{[a-z_]+\}")
NEGATIVE_PREFIX = "Does NOT "


def normalize(text: str) -> str:
    """Collapse whitespace and drop Markdown bold, the way rule_labels.rule_text renders a rule."""
    return " ".join(text.replace("**", "").split())


def load_templates(path: Path | None = None) -> dict[str, dict]:
    """The shared item templates keyed by id. Raises ValueError on a duplicate id."""
    templates: dict[str, dict] = {}
    for template in json.loads((path or TEMPLATES_PATH).read_text())["items"]:
        if template["id"] in templates:
            raise ValueError(f"duplicate template id {template['id']}")
        templates[template["id"]] = template
    return templates


def resolve_item(item: dict, templates: dict[str, dict]) -> tuple[dict, list[str]]:
    """The item with its template's fields filled in, plus problems (an unknown template)."""
    base_id = item.get("extends")
    if base_id is None:
        return dict(item), []
    template = templates.get(base_id)
    if template is None:
        return dict(item), [f"{item.get('id', '?')}: extends unknown template {base_id}"]
    merged = {key: value for key, value in template.items() if key != "id"}
    merged.update({key: value for key, value in item.items() if key != "extends"})
    merged["extends"] = base_id
    return merged, []


def resolve_rubric(rubric: dict, templates: dict[str, dict]) -> tuple[list[dict], list[str]]:
    """Every item of the rubric resolved against the templates, plus resolution problems."""
    items: list[dict] = []
    problems: list[str] = []
    for item in rubric.get("items") or []:
        resolved, found = resolve_item(item, templates)
        items.append(resolved)
        problems.extend(found)
    return items, problems


def item_problems(item: dict, coverage: dict[str, str], rule_text) -> list[str]:
    """What is wrong with one resolved item. rule_text maps a rule id to its text ("" when missing)."""
    label = item.get("id", "?")
    unknown = sorted(set(item) - set(FIELDS) - {"extends"})
    if unknown:
        return [f"{label}: unknown keys {', '.join(unknown)}"]
    missing = [field for field in FIELDS if not item.get(field)]
    if missing:
        return [f"{label}: missing {', '.join(missing)}"]
    wrong_type = [field for field in FIELDS if field != "rules" and not isinstance(item[field], str)]
    if wrong_type or not all(isinstance(rule, str) for rule in item["rules"]):
        return [f"{label}: rules must be a list of ids and every other field a string"]
    problems = [*field_value_problems(item), *rule_problems(item, coverage, rule_text)]
    return [f"{label}: {problem}" for problem in problems]


def field_value_problems(item: dict) -> list[str]:
    """Enumerated fields hold allowed values; ids are dotted slugs; no template placeholder is left."""
    problems = []
    if not ITEM_ID_RE.match(item["id"]):
        problems.append("id must be a dotted lowercase slug such as scope.no_new_env")
    if item["dimension"] not in DIMENSIONS:
        problems.append(f"dimension must be one of {', '.join(DIMENSIONS)}")
    if item["polarity"] not in POLARITIES:
        problems.append(f"polarity must be one of {', '.join(POLARITIES)}")
    if item["tier"] not in TIERS:
        problems.append(f"tier must be one of {', '.join(TIERS)}")
    is_negative = item["polarity"] == "negative"
    if is_negative != item["question"].startswith(NEGATIVE_PREFIX):
        problems.append(f"a negative item's question starts with '{NEGATIVE_PREFIX.strip()}', and only a negative one")
    unfilled = [field for field in ("question", "look_at", "yes_when", "no_when") if PLACEHOLDER_RE.search(item[field])]
    if unfilled:
        problems.append(f"fill the template placeholders in {', '.join(unfilled)}")
    return problems


def rule_problems(item: dict, coverage: dict[str, str], rule_text) -> list[str]:
    """Every rule id is known, and the key phrase is quoted verbatim from one of the item's rules."""
    unknown = [rule for rule in item["rules"] if rule not in coverage]
    if unknown:
        return [f"unknown rule ids {', '.join(unknown)}"]
    phrase = normalize(item["key_phrase"])
    if not any(phrase in normalize(rule_text(rule)) for rule in item["rules"]):
        return [f"key_phrase is not verbatim in {', '.join(item['rules'])}: {item['key_phrase']!r}"]
    return []


def rubric_problems(items: list[dict], coverage: dict[str, str], rule_text, readout: bool = False) -> list[str]:
    """Item-level problems plus the rubric-level ones: size, unique ids, at least one must-have item."""
    problems = [problem for item in items for problem in item_problems(item, coverage, rule_text)]
    low, high = READOUT_ITEMS if readout else (MIN_ITEMS, MAX_ITEMS)
    if not low <= len(items) <= high:
        kind = "a readout rubric" if readout else "a rubric"
        problems.append(f"has {len(items)} items; {kind} holds {low} to {high}")
    ids = [item.get("id") for item in items]
    duplicates = sorted({item_id for item_id in ids if ids.count(item_id) > 1 and item_id})
    if duplicates:
        problems.append(f"duplicate item ids {', '.join(duplicates)}")
    if not any(item.get("tier") == "must" for item in items):
        problems.append("needs at least one must-have item")
    return problems


def template_problems(templates: dict[str, dict], coverage: dict[str, str], rule_text) -> list[str]:
    """Templates carry every field and quote their rules verbatim; placeholders are allowed here."""
    problems = []
    for template in templates.values():
        filled = {
            key: PLACEHOLDER_RE.sub("x", value) if isinstance(value, str) else value for key, value in template.items()
        }
        problems.extend(f"template {problem}" for problem in item_problems(filled, coverage, rule_text))
    return problems


def task_items(task: str, rule_text) -> tuple[list[dict] | None, list[str]]:
    """The task's resolved items and their problems; (None, []) when the task has no rubric yet."""
    path = RUBRICS_DIR / f"{task}.json"
    if not path.is_file():
        return None, []
    coverage = json.loads(RULES_PATH.read_text())
    try:
        templates = load_templates(TEMPLATES_PATH)
    except ValueError as error:
        return None, [str(error)]
    source = json.loads(path.read_text())
    items, problems = resolve_rubric(source, templates)
    return items, problems + rubric_problems(items, coverage, rule_text, readout=bool(source.get("readout")))


def is_readout(task: str) -> bool:
    """The task's rubric is a zero-weight readout (see the module docstring)."""
    path = RUBRICS_DIR / f"{task}.json"
    return path.is_file() and bool(json.loads(path.read_text()).get("readout"))


def items_json(items: list[dict]) -> bytes:
    """The resolved items as the judge runner reads them, stable across runs."""
    return (json.dumps({"items": items}, indent=2, sort_keys=True) + "\n").encode()
