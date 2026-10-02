#!/usr/bin/env python3
"""Trigger suite: does Claude Code load the right Consult skill before it first writes?

  uv run --project eval eval/scripts/triggers.py --dry-run
  uv run --project eval eval/scripts/triggers.py --wiring-check --arms plugin,skills,bare
  uv run --project eval eval/scripts/triggers.py --arms plugin --attempts 3 --model claude-opus-5-5

Each case x attempt x arm runs `claude -p` once in a fresh container built from
the case's workspace (eval/triggers/cases.yaml). Arms:
  plugin  the real plugin: this repo's plugin/ (or --plugin) mounted read-only
          and passed with --plugin-dir, as an installed plugin loads
  skills  Harbor's wiring: agents/.agents/skills copied into CLAUDE_CONFIG_DIR/skills
          and the SessionStart hook passed through --settings
  bare    neither
Nothing from the host's ~/.claude enters the container. CLAUDE_CODE_OAUTH_TOKEN
reaches it by name only (`docker run -e CLAUDE_CODE_OAUTH_TOKEN`).

Positive cases stop at the first write: the container is killed when the first
write call arrives. Negative cases run to the end. A load is a Skill call that
names a catalog skill (consult: prefix optional), or a Read or Bash call whose
arguments mention skills/<name>/SKILL.md, unless its tool_result is an error
(an unknown skill, a missing file). A plain name that reaches another skill is
not a load: one listed beside its consult: twin, or, outside the skills arm, a
skill the CLI bundles. The catalog is the directory names under
agents/.agents/skills.

Write detection. A write is a Write, Edit, MultiEdit, or NotebookEdit call, or a
Bash command that, after quoted strings are blanked, contains an output
redirection to a file (>, >>, 2>, &>, and so on, except to /dev/null or another
descriptor) or a command segment that passes --write or starts with mv, cp, rm,
tee, mkdir, `sed -i`, `git ... commit|mv|rm`, `npm install`/`npm i`,
`npm version <version>`, or `npm pkg set|delete`. Inline interpreter code
(python -c, python - <<EOF, node -e, perl -pi) is a write when it calls a
file-writing API: write_text, writeFileSync, open(path, "w"), rename, unlink,
and similar. Writes hidden behind a script file the agent runs are missed.

Scoring. An error trial (no init event, no result event, or an api_error
result) is left out of the metrics, except a negative that already loaded a
skill: nothing after the error can undo that false trigger. Verdicts compare
the point estimate with the threshold; report.md also says whether the whole
Wilson interval meets it.

--wiring-check makes no model call: it runs each arm without the token, so
Claude Code prints its init and hook events and then fails at auth. It checks
that the plugin arm lists consult:* skills, the skills arm lists the plain
names, both fire the hook, and the bare arm has neither.

Output: eval/runs/triggers/<timestamp>-<label>/ with transcripts/, results.json,
and report.md. Exit 0 only when every Consult arm (plugin or skills) passes. A
failed threshold exits 1, and so does an arm left incomplete because a metric
has no data (every trial errored, or the selected cases lack a kind).
"""

from __future__ import annotations

import argparse
import datetime as dt
import fnmatch
import json
import math
import os
import re
import shlex
import shutil
import statistics
import subprocess
import tempfile
import threading
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from itertools import chain, dropwhile, product
from pathlib import Path, PurePosixPath
from typing import Iterable, Optional

EVAL_DIR = Path(__file__).resolve().parent.parent
REPO_DIR = EVAL_DIR.parent
SKILLS_DIR = REPO_DIR / "agents" / ".agents" / "skills"
PLUGIN_DIR = REPO_DIR / "plugin"
TASKS_DIR = EVAL_DIR / "tasks"
CASES_PATH = EVAL_DIR / "triggers" / "cases.yaml"
FIXTURES_DIR = EVAL_DIR / "triggers" / "fixtures"
SHARED_DOCKERFILE = EVAL_DIR / "verifier" / "shared" / "Dockerfile"
AGENT_CONFIG = EVAL_DIR / "agents" / "claude-code.yaml"
RUNS_DIR = EVAL_DIR / "runs" / "triggers"

ARMS = ("plugin", "skills", "bare")
CONSULT_ARMS = ("plugin", "skills")
KINDS = ("positive", "negative")
EFFORTS = ("low", "medium", "high", "xhigh", "max")
METRICS = ("workflow_recall", "narrow_recall", "false_trigger_rate")
IMAGE_PREFIX = "consult-trigger"
PREFIX = "consult:"
HOOK_MARKER = "Consult is installed"
# Claude Code 2.1.282 bundles its own code-review skill, listed in every arm.
CLI_BUNDLED_SKILLS = frozenset({"code-review"})
TRIAL_TIMEOUT_SEC = 1800
WIRING_TIMEOUT_SEC = 180

# Container layout, mirroring Harbor's claude_code agent: its config dir, its
# default injected-skills dir, and the path it passes to --settings.
WORKDIR = "/app"
CONFIG_DIR = "/logs/agent/sessions"
HARBOR_SKILLS_DIR = "/harbor/skills"
SETTINGS_PATH = "/tmp/claude-code-settings/settings.json"
PLUGIN_MOUNT = "/opt/consult-plugin"
# Harbor's env for every arm, so arms differ only in Consult wiring. IS_SANDBOX
# lets root use bypassPermissions.
CONTAINER_ENV = {
    "IS_SANDBOX": "1",
    "CLAUDE_CONFIG_DIR": CONFIG_DIR,
    "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1",
    "FORCE_AUTO_BACKGROUND_TASKS": "1",
    "ENABLE_BACKGROUND_TASKS": "1",
}
CONFIG_SETUP = "mkdir -p " + " ".join(
    f"$CLAUDE_CONFIG_DIR/{d}" for d in ("debug", "projects/-app", "shell-snapshots", "statsig", "todos", "skills"))
ARM_SETUP = {"skills": f"cp -r {HARBOR_SKILLS_DIR}/* $CLAUDE_CONFIG_DIR/skills/"}
ARM_FLAGS = {"plugin": ["--plugin-dir", PLUGIN_MOUNT], "skills": ["--settings", SETTINGS_PATH], "bare": []}

WRITE_TOOLS = frozenset({"Write", "Edit", "MultiEdit", "NotebookEdit"})
LOAD_TOOLS = frozenset({"Skill", "SlashCommand"})
PATH_TOOLS = frozenset({"Read", "Bash"})
SKILL_PATH_RE = re.compile(r"skills/([a-z][a-z0-9-]*)/SKILL\.md")
STEP_NAME_RE = re.compile(r'^\[\[steps\]\]\s*\n\s*name\s*=\s*"([^"]+)"', re.MULTILINE)
QUOTED_RE = re.compile(r"'[^']*'|\"(?:[^\"\\]|\\.)*\"")
SEGMENT_RE = re.compile(r"&&|\|\||[;|&\n()]")
REDIRECT_RE = re.compile(r"(?<![=<>-])>>?(?![&>=])\s*(?!/dev/null\b)[^\s&|;<>]")
INLINE_CODE_RE = re.compile(r"\b(?:python3?|node|perl|ruby)\b[^\n]*?(?:\s-(?:c|e|pi?)\b|\s-(?:\s|$)|<<)")
CODE_WRITE_RE = re.compile(
    r"(?<!stdout\.)(?<!stderr\.)\bwrite(?:FileSync|File|_text|_bytes)?\s*\(|appendFile|\bopen\([^)]*,\s*['\"][wax]"
    r"|\brename(?:Sync)?\(|\bunlink(?:Sync)?\(|\brmSync\(|\bos\.remove\(|\bshutil\.(?:copy|move|rmtree)|\s-pi\b"
)
BASH_WRITE_COMMANDS = frozenset({"mv", "cp", "rm", "tee", "mkdir"})
GIT_WRITE_SUBCOMMANDS = frozenset({"commit", "mv", "rm"})


@dataclass(frozen=True)
class Case:
    name: str
    kind: str
    source_kind: str
    source: str
    prompt: str
    code_change: bool
    required_any: tuple = ()
    expect_silent: tuple = ()
    edits: tuple = ()
    uncommitted: tuple = ()


@dataclass(frozen=True)
class Suite:
    confidence: float
    thresholds: dict
    cases: tuple


@dataclass(frozen=True)
class RunConfig:
    model: str
    effort: Optional[str]
    max_turns: int
    max_budget_usd: float
    plugin_dir: Path
    settings_file: Path


@dataclass(frozen=True)
class Trial:
    case: Case
    arm: str
    attempt: int
    image: str


# ---------------------------------------------------------------- cases file

def catalog(skills_dir: Path = SKILLS_DIR) -> frozenset:
    return frozenset(p.parent.name for p in skills_dir.glob("*/SKILL.md"))


def suite_problems(doc: dict, names: frozenset) -> list:
    """Everything wrong with a parsed cases file; empty when it is valid."""
    if not isinstance(doc, dict):
        return ["the cases file is not a mapping"]
    raw_cases = doc.get("cases") or []
    counts = Counter(c.get("name") for c in raw_cases if isinstance(c, dict))
    problems = threshold_problems(doc)
    problems += [f"duplicate case name {n!r}" for n, k in counts.items() if k > 1]
    return problems + list(chain.from_iterable(case_problems(c, names) for c in raw_cases))


def threshold_problems(doc: dict) -> list:
    thresholds = doc.get("thresholds") or {}
    confidence = doc.get("confidence")
    problems = [] if isinstance(confidence, float) and 0 < confidence < 1 else ["confidence must be a fraction"]
    wanted = {"workflow_recall": "min", "narrow_recall": "min", "false_trigger_rate": "max"}
    problems += [f"thresholds.{m} needs a {b} fraction" for m, b in wanted.items()
                 if not isinstance((thresholds.get(m) or {}).get(b), (int, float))]
    if not isinstance(thresholds.get("negative_case_max_triggered"), int):
        problems.append("thresholds.negative_case_max_triggered must be an integer")
    return problems


def case_problems(raw: dict, names: frozenset) -> list:
    if not isinstance(raw, dict):
        return [f"case {raw!r} is not a mapping"]
    label = raw.get("name") or "<unnamed>"
    problems = shape_problems(raw) + source_problems(raw)
    skills = [*(raw.get("required_any") or []), *(raw.get("expect_silent") or [])]
    problems += [f"unknown skill {s!r}" for s in skills if s not in names]
    if not problems:
        problems = edit_problems(to_case(raw))
    return [f"{label}: {p}" for p in problems]


def shape_problems(raw: dict) -> list:
    problems = [] if isinstance(raw.get("name"), str) and raw["name"] else ["name is required"]
    if raw.get("kind") not in KINDS:
        problems.append(f"kind must be one of {KINDS}")
    if not isinstance(raw.get("code_change"), bool):
        problems.append("code_change must be true or false")
    required = raw.get("required_any") or []
    if raw.get("kind") == "positive" and not required:
        problems.append("a positive case needs required_any")
    if raw.get("kind") == "negative" and required:
        problems.append("a negative case takes no required_any")
    if set(required) & set(raw.get("expect_silent") or []):
        problems.append("a skill is both required_any and expect_silent")
    return problems


def source_problems(raw: dict) -> list:
    source = raw.get("source") or {}
    if not isinstance(source, dict) or len(source) != 1 or next(iter(source)) not in ("task", "fixture"):
        return ["source must be {task: <name>} or {fixture: <name>}"]
    kind, name = next(iter(source.items()))
    if kind == "task" and not (TASKS_DIR / str(name) / "task.toml").is_file():
        return [f"no eval task {name!r}"]
    if kind == "fixture" and not (FIXTURES_DIR / str(name)).is_dir():
        return [f"no fixture {name!r}"]
    if kind == "fixture" and not raw.get("prompt"):
        return ["a fixture case needs a prompt"]
    edits = [*(raw.get("edits") or []), *(raw.get("uncommitted") or [])]
    return list(chain.from_iterable(map(edit_shape_problems, edits)))


def edit_shape_problems(edit: dict) -> list:
    if not isinstance(edit, dict) or not isinstance(edit.get("path"), str):
        return [f"edit {edit!r} needs a path"]
    path = PurePosixPath(edit["path"])
    if path.is_absolute() or ".." in path.parts:
        return [f"edit path {edit['path']!r} must stay inside the workspace"]
    replace = edit.get("replace")
    has_replace = isinstance(replace, list) and len(replace) == 2 and all(isinstance(s, str) for s in replace)
    if has_replace == isinstance(edit.get("content"), str):
        return [f"edit {edit['path']!r} needs exactly one of replace: [old, new] or content"]
    return []


def edit_problems(case: Case) -> list:
    """Materialize the build context once so a stale replace fails validation, not the run."""
    with tempfile.TemporaryDirectory(prefix="consult-trigger-check-") as tmp:
        try:
            materialize(case, Path(tmp))
        except ValueError as exc:
            return [str(exc)]
    return []


def to_case(raw: dict) -> Case:
    kind, name = next(iter(raw["source"].items()))
    return Case(
        name=raw["name"], kind=raw["kind"], source_kind=kind, source=str(name),
        prompt=(raw.get("prompt") or task_prompt(str(name))).strip(),
        code_change=raw["code_change"],
        required_any=tuple(raw.get("required_any") or ()),
        expect_silent=tuple(raw.get("expect_silent") or ()),
        edits=tuple(raw.get("edits") or ()),
        uncommitted=tuple(raw.get("uncommitted") or ()),
    )


def task_prompt(task: str) -> str:
    """The task's first-turn instruction: steps/<first step>/instruction.md for a multi-step task."""
    task_dir = TASKS_DIR / task
    steps = STEP_NAME_RE.findall((task_dir / "task.toml").read_text())
    path = task_dir / "steps" / steps[0] / "instruction.md" if steps else task_dir / "instruction.md"
    return path.read_text()


def load_suite(path: Path = CASES_PATH, names: Optional[frozenset] = None) -> Suite:
    import yaml  # the runner needs pyyaml; the scoring code and its tests do not

    doc = yaml.safe_load(path.read_text())
    problems = suite_problems(doc, names or catalog())
    if problems:
        raise SystemExit(f"{path} is invalid:\n  " + "\n  ".join(problems))
    cases = tuple(to_case(raw) for raw in doc["cases"])
    return Suite(confidence=doc["confidence"], thresholds=doc["thresholds"], cases=cases)


# ---------------------------------------------------------- build contexts

def image_tag(case: Case) -> str:
    if case.edits or case.uncommitted:
        return f"{IMAGE_PREFIX}/case-{case.name}"
    return f"{IMAGE_PREFIX}/{case.source}" if case.source_kind == "task" else f"{IMAGE_PREFIX}/fixture-{case.source}"


def needs_context(case: Case) -> bool:
    """A task with no edits builds from its own environment dir; everything else from a temp context."""
    return case.source_kind == "fixture" or bool(case.edits or case.uncommitted)


def materialize(case: Case, dest: Path) -> Path:
    """Write the case's build context: Dockerfile, workspace/, and uncommitted/ when the tree must be dirty."""
    task_env = TASKS_DIR / case.source / "environment"
    workspace = task_env / "workspace" if case.source_kind == "task" else FIXTURES_DIR / case.source
    dockerfile = (task_env / "Dockerfile" if case.source_kind == "task" else SHARED_DOCKERFILE).read_text()
    shutil.copytree(workspace, dest / "workspace")
    for edit in case.edits:
        apply_edit(dest / "workspace", dest / "workspace", edit)
    for edit in case.uncommitted:
        apply_edit(dest / "uncommitted", dest / "workspace", edit)
    if case.uncommitted:
        dockerfile += "\n# Copied after the scaffold commit: the case needs a dirty working tree.\nCOPY uncommitted/ /app/\n"
    (dest / "Dockerfile").write_text(dockerfile)
    return dest


def apply_edit(root: Path, base: Path, edit: dict) -> None:
    """Write one edit under root; a replace reads root's copy of the file when present, else base's."""
    target = root / edit["path"]
    source = target if target.is_file() else base / edit["path"]
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(edited_text(source, edit))


def edited_text(source: Path, edit: dict) -> str:
    if "content" in edit:
        return edit["content"]
    old, new = edit["replace"]
    text = source.read_text() if source.is_file() else ""
    if text.count(old) != 1:
        raise ValueError(f"{edit['path']}: expected {old!r} once, found it {text.count(old)} times")
    return text.replace(old, new)


# ------------------------------------------------------- transcript scoring

def parse_line(line: str) -> Optional[dict]:
    try:
        event = json.loads(line)
    except json.JSONDecodeError:
        return None
    return event if isinstance(event, dict) else None


def parse_stream(lines: Iterable[str]) -> list:
    return [e for e in map(parse_line, lines) if e is not None]


def event_tool_uses(event: dict) -> list:
    """tool_use blocks of one assistant event, in order; subagent calls included."""
    if event.get("type") != "assistant":
        return []
    content = (event.get("message") or {}).get("content") or []
    return [b for b in content if isinstance(b, dict) and b.get("type") == "tool_use"]


def tool_calls(events: list) -> list:
    return list(chain.from_iterable(map(event_tool_uses, events)))


def first_event(events: list, kind: str, subtype: Optional[str] = None) -> Optional[dict]:
    return next((e for e in events if e.get("type") == kind and subtype in (None, e.get("subtype"))), None)


def last_event(events: list, kind: str) -> Optional[dict]:
    return next((e for e in reversed(events) if e.get("type") == kind), None)


def bash_writes(command: str) -> bool:
    """Whether a shell command clearly writes files; the rules are in the module docstring."""
    text = QUOTED_RE.sub("''", command)
    if REDIRECT_RE.search(text) or inline_code_writes(command):
        return True
    return any(segment_writes(segment.split()) for segment in SEGMENT_RE.split(text))


def inline_code_writes(command: str) -> bool:
    """Interpreter code passed inline (quoted or as a heredoc) that calls a file-writing API."""
    return bool(INLINE_CODE_RE.search(command) and CODE_WRITE_RE.search(command))


def segment_writes(tokens: list) -> bool:
    words = list(dropwhile(lambda t: "=" in t or t == "sudo", tokens))
    if not words:
        return False
    command, rest = words[0].rsplit("/", 1)[-1], words[1:]
    if command in BASH_WRITE_COMMANDS or "--write" in rest:
        return True
    if command == "sed":
        return any(w.startswith("-i") or w == "--in-place" for w in rest)
    if command == "git":
        return bool(GIT_WRITE_SUBCOMMANDS & set(rest))
    return command == "npm" and npm_writes(rest)


def npm_writes(rest: list) -> bool:
    sub, args = (rest[0], rest[1:]) if rest else ("", [])
    if sub == "version":
        return any(not a.startswith("-") for a in args)
    return sub in ("install", "i") or (sub == "pkg" and args[:1] in (["set"], ["delete"]))


def is_write_call(call: dict) -> bool:
    name = call.get("name")
    if name in WRITE_TOOLS:
        return True
    command = (call.get("input") or {}).get("command")
    return name == "Bash" and isinstance(command, str) and bash_writes(command)


def shadowed_names(init: dict, arm: str) -> frozenset:
    """Plain names that reach a skill other than Consult's: one listed beside its consult: twin, and outside the
    skills arm (the only arm that installs Consult under plain names) a skill the CLI bundles."""
    listed = set(init.get("skills") or [])
    twins = {s for s in listed if PREFIX not in s and f"{PREFIX}{s}" in listed}
    return frozenset(twins | (set() if arm == "skills" else CLI_BUNDLED_SKILLS))


def failed_call_ids(events: list) -> frozenset:
    """ids of the tool calls whose tool_result is an error."""
    return frozenset(chain.from_iterable(map(event_failed_ids, events)))


def event_failed_ids(event: dict) -> list:
    content = (event.get("message") or {}).get("content") if event.get("type") == "user" else None
    if not isinstance(content, list):
        return []
    return [b["tool_use_id"] for b in content if isinstance(b, dict) and b.get("type") == "tool_result"
            and b.get("is_error") and b.get("tool_use_id")]


def loaded_skills(call: dict, names: frozenset, shadowed: frozenset) -> list:
    args = call.get("input") or {}
    if call.get("name") in LOAD_TOOLS:
        return invoked_skill(args, names, shadowed)
    if call.get("name") in PATH_TOOLS:
        text = " ".join(v for v in args.values() if isinstance(v, str))
        return [n for n in dict.fromkeys(SKILL_PATH_RE.findall(text)) if n in names]
    return []


def invoked_skill(args: dict, names: frozenset, shadowed: frozenset) -> list:
    raw = str(args.get("skill") or args.get("name") or args.get("command") or "").strip().lstrip("/")
    token = raw.split()[0] if raw else ""
    prefixed = token.startswith(PREFIX)
    name = token[len(PREFIX):] if prefixed else token
    return [name] if name in names and (prefixed or name not in shadowed) else []


def score_calls(calls: list, names: frozenset, shadowed: frozenset, failed: frozenset = frozenset()) -> dict:
    """Consult loads in call order, each marked on time when it came before the first write.

    A call in failed (its tool_result is an error) loads nothing. A call with no result yet, such as one cut off
    by the stop at the first write, still counts."""
    first_write = next((i for i, c in enumerate(calls) if is_write_call(c)), None)

    def loads_at(index: int, call: dict) -> list:
        if call.get("id") in failed:
            return []
        on_time = first_write is None or index < first_write
        return [{"skill": s, "call": index, "on_time": on_time} for s in loaded_skills(call, names, shadowed)]

    loads = list(chain.from_iterable(loads_at(i, c) for i, c in enumerate(calls)))
    return {"first_write": first_write, "loads": loads}


def call_summary(call: dict) -> dict:
    args = call.get("input") or {}
    detail = args.get("skill") or args.get("file_path") or args.get("command") or args.get("pattern") or ""
    return {"tool": call.get("name"), "detail": str(detail)[:160]}


def hook_fired(events: list) -> bool:
    return any(e.get("subtype") == "hook_response" and e.get("hook_event") == "SessionStart"
               and HOOK_MARKER in str(e.get("output") or "") for e in events)


def run_facts(events: list) -> dict:
    """Model, effort evidence, and the result event's accounting."""
    init = first_event(events, "system", "init") or {}
    result = last_event(events, "result") or {}
    return {
        "model": init.get("model"),
        "effort_evidence": {k: v for k, v in init.items() if "effort" in k.lower()},
        "cli_version": init.get("claude_code_version"),
        "models_used": sorted((result.get("modelUsage") or {}).keys()),
        "result_subtype": result.get("subtype"),
        "terminal_reason": result.get("terminal_reason"),
        "num_turns": result.get("num_turns"),
        "cost_usd": result.get("total_cost_usd"),
        "duration_ms": result.get("duration_ms"),
    }


def trial_outcome(events: list, stopped: bool, timed_out: bool) -> str:
    """stopped_at_write, completed, timed_out, or error (no init, no result, or an API failure); see counted."""
    if stopped:
        return "stopped_at_write"
    if first_event(events, "system", "init") is None:
        return "error"
    if timed_out:
        return "timed_out"
    result = last_event(events, "result")
    if result is None or result.get("terminal_reason") == "api_error":
        return "error"
    return "completed"


def trial_record(case: Case, arm: str, attempt: int, events: list, names: frozenset,
                 stopped: bool = False, timed_out: bool = False) -> dict:
    init = first_event(events, "system", "init") or {}
    calls = tool_calls(events)
    scored = score_calls(calls, names, shadowed_names(init, arm), failed_call_ids(events))
    on_time = {load["skill"] for load in scored["loads"] if load["on_time"]}
    loaded = {load["skill"] for load in scored["loads"]}
    return {
        "case": case.name, "arm": arm, "attempt": attempt, "kind": case.kind, "code_change": case.code_change,
        "outcome": trial_outcome(events, stopped, timed_out),
        "hook_fired": hook_fired(events),
        "workflow_on_time": "workflow" in on_time,
        "required_hit": bool(on_time & set(case.required_any)),
        "any_load": bool(loaded),
        "off_target": sorted(loaded & set(case.expect_silent)),
        **scored,
        "calls": [call_summary(c) for c in calls],
        **run_facts(events),
    }


# ------------------------------------------------------------------ metrics

def wilson(hits: int, n: int, confidence: float) -> Optional[tuple]:
    if n == 0:
        return None
    z = statistics.NormalDist().inv_cdf(0.5 + confidence / 2)
    p = hits / n
    denom = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return (max(0.0, center - half), min(1.0, center + half))


def proportion(trials: list, hit, confidence: float) -> dict:
    hits = sum(1 for t in trials if hit(t))
    n = len(trials)
    return {"hits": hits, "n": n, "rate": hits / n if n else None, "interval": wilson(hits, n, confidence)}


def meets(low: float, high: float, bound: dict) -> bool:
    return low >= bound["min"] if "min" in bound else high <= bound["max"]


def judged(measure: dict, bound: dict) -> dict:
    """The verdict judges the point estimate; bound_clears says whether the whole interval meets the threshold."""
    if not measure["n"]:
        return {**measure, "threshold": bound, "verdict": "no data", "bound_clears": None}
    rate = measure["rate"]
    return {**measure, "threshold": bound, "verdict": "pass" if meets(rate, rate, bound) else "fail",
            "bound_clears": meets(*measure["interval"], bound)}


def failing_negatives(negatives: list, max_triggered: int) -> list:
    triggered = Counter(t["case"] for t in negatives if t["any_load"])
    return sorted(case for case, count in triggered.items() if count > max_triggered)


def counted(trial: dict) -> bool:
    """Whether a trial enters the metrics. An error trial enters only as a negative that already loaded a skill."""
    return trial["outcome"] != "error" or (trial["kind"] == "negative" and trial["any_load"])


def arm_metrics(trials: list, thresholds: dict, confidence: float) -> dict:
    """Pass or fail per pre-registered metric over one arm's trials; uncounted error trials are reported."""
    valid = [t for t in trials if counted(t)]
    positives = [t for t in valid if t["kind"] == "positive"]
    negatives = [t for t in valid if t["kind"] == "negative"]
    measures = {
        "workflow_recall": proportion([t for t in positives if t["code_change"]], lambda t: t["workflow_on_time"],
                                      confidence),
        "narrow_recall": proportion(positives, lambda t: t["required_hit"], confidence),
        "false_trigger_rate": proportion(negatives, lambda t: t["any_load"], confidence),
    }
    metrics = {k: judged(m, thresholds[k]) for k, m in measures.items()}
    failing = failing_negatives(negatives, thresholds["negative_case_max_triggered"])
    return {
        **metrics,
        "off_target": {**proportion(positives, lambda t: bool(t["off_target"]), confidence),
                       "skills": dict(Counter(chain.from_iterable(t["off_target"] for t in positives)))},
        "failing_negative_cases": failing,
        "errors": len(trials) - len(valid),
        "overall": overall_verdict([m["verdict"] for m in metrics.values()], failing),
    }


def overall_verdict(verdicts: list, failing_negative_cases: list) -> str:
    if failing_negative_cases or "fail" in verdicts:
        return "fail"
    return "pass" if all(v == "pass" for v in verdicts) else "incomplete"


# ------------------------------------------------------------------- report

def percent(value: Optional[float]) -> str:
    return "n/a" if value is None else f"{value:.0%}"


def interval_text(bounds: Optional[tuple]) -> str:
    return "n/a" if bounds is None else f"{bounds[0]:.0%} to {bounds[1]:.0%}"


def threshold_text(bound: dict) -> str:
    return f">= {bound['min']:.0%}" if "min" in bound else f"<= {bound['max']:.0%}"


def metric_row(name: str, m: dict) -> str:
    clears = {True: "yes", False: "no", None: "n/a"}[m["bound_clears"]]
    return (f"| {name} | {m['hits']}/{m['n']} | {percent(m['rate'])} | {interval_text(m['interval'])} "
            f"| {threshold_text(m['threshold'])} | {m['verdict']} | {clears} |")


def metric_rows(metrics: dict, confidence: float) -> list:
    lines = [f"| metric | hits/n | rate | {confidence:.0%} Wilson | threshold | verdict | interval meets threshold |",
             "| --- | ---: | ---: | --- | --- | --- | --- |"]
    lines += [metric_row(name, metrics[name]) for name in METRICS]
    off = metrics["off_target"]
    skills = ", ".join(f"{s} ({n})" for s, n in sorted(off["skills"].items())) or "none"
    lines.append(f"| off_target (descriptive) | {off['hits']}/{off['n']} | {percent(off['rate'])} "
                 f"| {interval_text(off['interval'])} | none | {skills} | - |")
    return lines


def load_order(trial: dict) -> str:
    """Loads in call order; * marks one after the first write. An error trial shows the loads it made first."""
    order = " > ".join(f"{l['skill']}{'' if l['on_time'] else '*'}" for l in trial["loads"])
    if trial["outcome"] == "error":
        return f"error after {order}" if order else "error"
    return order or "none"


def case_row(case: str, trials: list) -> str:
    valid = [t for t in trials if counted(t)]
    kind = trials[0]["kind"]
    counts_workflow = kind == "positive" and trials[0]["code_change"]
    workflow = f"{sum(t['workflow_on_time'] for t in valid)}/{len(valid)}" if counts_workflow else "-"
    required = f"{sum(t['required_hit'] for t in valid)}/{len(valid)}" if kind == "positive" else "-"
    false_triggers = f"{sum(t['any_load'] for t in valid)}/{len(valid)}" if kind == "negative" else "-"
    loads = " / ".join(load_order(t) for t in sorted(trials, key=lambda t: t["attempt"]))
    return f"| {case} | {kind} | {len(trials)} | {workflow} | {required} | {false_triggers} | {loads} |"


def case_table(trials: list) -> list:
    by_case: dict = {}
    for trial in trials:
        by_case.setdefault(trial["case"], []).append(trial)
    lines = ["| case | kind | attempts | workflow on time | required hit | false triggers | loads in order (per attempt) |",
             "| --- | --- | ---: | ---: | ---: | ---: | --- |"]
    return lines + [case_row(case, rows) for case, rows in by_case.items()]


def cost_line(trials: list) -> str:
    known = [t["cost_usd"] for t in trials if t.get("cost_usd") is not None]
    return f"Cost: ${sum(known):.2f} over {len(known)} of {len(trials)} trials (a trial stopped at its first write reports none)."


def render_arm(arm: str, trials: list, metrics: dict, confidence: float) -> list:
    failing = ", ".join(metrics["failing_negative_cases"]) or "none"
    lines = [f"## Arm: {arm}", "", f"Overall: **{metrics['overall']}**. Negative cases triggered in 2+ attempts: "
             f"{failing}. Error trials excluded: {metrics['errors']}.", ""]
    lines += metric_rows(metrics, confidence) + [""] + case_table(trials) + ["", cost_line(trials), ""]
    return lines


def render_report(results: dict) -> str:
    run = results["run"]
    header = [f"# Trigger suite: {run['label']}", "",
              f"Model {run['model']}, effort {run['effort'] or 'CLI default'}, {run['attempts']} attempts, "
              f"max turns {run['max_turns']}, budget ${run['max_budget_usd']} per trial. "
              "Loads marked * came after the first write. The bare arm is the control; thresholds judge the Consult arms. "
              "A verdict compares the point estimate with the threshold; the last column says whether the whole "
              "Wilson interval also meets it.", ""]
    body = [render_arm(arm, [t for t in results["trials"] if t["arm"] == arm], results["metrics"][arm],
                       results["confidence"]) for arm in run["arms"]]
    return "\n".join(header + list(chain.from_iterable(body)))


# ------------------------------------------------------------------- docker

def claude_args(prompt: str, run: RunConfig, arm: str) -> list:
    effort = ["--effort", run.effort] if run.effort else []
    return ["-p", prompt, "--model", run.model, *effort, "--output-format", "stream-json", "--verbose",
            "--include-hook-events", "--permission-mode", "bypassPermissions", "--max-turns", str(run.max_turns),
            "--max-budget-usd", str(run.max_budget_usd), *ARM_FLAGS[arm]]


def arm_mounts(arm: str, run: RunConfig) -> list:
    if arm == "plugin":
        return ["-v", f"{run.plugin_dir}:{PLUGIN_MOUNT}:ro"]
    if arm == "skills":
        return ["-v", f"{SKILLS_DIR}:{HARBOR_SKILLS_DIR}:ro", "-v", f"{run.settings_file}:{SETTINGS_PATH}:ro"]
    return []


def docker_argv(image: str, container: str, arm: str, run: RunConfig, prompt: str, with_token: bool) -> list:
    """docker run for one trial. The token is passed by name, so its value never appears in argv."""
    env = list(chain.from_iterable(["-e", f"{k}={v}"] for k, v in CONTAINER_ENV.items()))
    token = ["-e", "CLAUDE_CODE_OAUTH_TOKEN"] if with_token else []
    script = " && ".join([CONFIG_SETUP, *([ARM_SETUP[arm]] if arm in ARM_SETUP else []), 'exec claude "$@"'])
    return ["docker", "run", "--rm", "--name", container, "-w", WORKDIR, *env, *token, *arm_mounts(arm, run),
            image, "sh", "-c", script, "claude", *claude_args(prompt, run, arm)]


def docker_build(tag: str, context: Path) -> None:
    proc = subprocess.run(["docker", "build", "-q", "-t", tag, str(context)], capture_output=True, text=True)
    if proc.returncode:
        raise SystemExit(f"docker build {tag} failed:\n{proc.stderr[-3000:]}")


def build_image(case: Case) -> str:
    tag = image_tag(case)
    if not needs_context(case):
        docker_build(tag, TASKS_DIR / case.source / "environment")
        return tag
    with tempfile.TemporaryDirectory(prefix="consult-trigger-") as tmp:
        docker_build(tag, materialize(case, Path(tmp)))
    return tag


def build_images(cases: Iterable[Case]) -> None:
    """Build each distinct image once; Docker's layer cache makes a rebuild cheap."""
    for tag, case in {image_tag(c): c for c in cases}.items():
        print(f"building {tag}", flush=True)
        build_image(case)


def kill(container: str) -> None:
    subprocess.run(["docker", "kill", container], capture_output=True)


def pump(stdout, transcript, container: str, stop_at_write: bool) -> tuple:
    """Copy the stream to the transcript line by line; kill the container at the first write when asked."""
    events, stopped = [], False
    for line in stdout:
        transcript.write(line)
        event = parse_line(line)
        if event is None:
            continue
        events.append(event)
        if stop_at_write and not stopped and any(map(is_write_call, event_tool_uses(event))):
            stopped = True
            kill(container)
    return events, stopped


def stream_container(argv: list, container: str, transcript: Path, stop_at_write: bool) -> tuple:
    timed_out = threading.Event()

    def on_timeout() -> None:
        timed_out.set()
        kill(container)

    timer = threading.Timer(TRIAL_TIMEOUT_SEC, on_timeout)
    with transcript.open("w") as out, transcript.with_suffix(".stderr").open("w") as err:
        proc = subprocess.Popen(argv, stdout=subprocess.PIPE, stderr=err, text=True)
        timer.start()
        try:
            events, stopped = pump(proc.stdout, out, container, stop_at_write)
        finally:
            proc.wait()
            timer.cancel()
    return events, stopped, timed_out.is_set()


def container_name(stamp: str, trial: Trial) -> str:
    return f"{IMAGE_PREFIX}-{stamp}-{os.getpid()}-{trial.case.name}-{trial.arm}-{trial.attempt}"


def run_trial(trial: Trial, run: RunConfig, names: frozenset, out_dir: Path, stamp: str) -> dict:
    transcript = out_dir / "transcripts" / f"{trial.case.name}__{trial.arm}__{trial.attempt}.jsonl"
    container = container_name(stamp, trial)
    argv = docker_argv(trial.image, container, trial.arm, run, trial.case.prompt, with_token=True)
    started = time.monotonic()
    events, stopped, timed_out = stream_container(argv, container, transcript, trial.case.kind == "positive")
    record = trial_record(trial.case, trial.arm, trial.attempt, events, names, stopped, timed_out)
    record.update(wall_seconds=round(time.monotonic() - started, 1), transcript=str(transcript.relative_to(out_dir)))
    print(f"{trial.case.name} {trial.arm} #{trial.attempt}: {record['outcome']}, loads {load_order(record)}", flush=True)
    return record


# ------------------------------------------------------------ wiring check

def listed_consult(init: dict, names: frozenset) -> dict:
    listed = set(init.get("skills") or [])
    return {
        "prefixed": {s[len(PREFIX):] for s in listed if s.startswith(PREFIX)} & names,
        "plain": listed & names,
        "plugin": any(p.get("name") == "consult" for p in init.get("plugins") or [] if isinstance(p, dict)),
    }


def expected_wiring(arm: str, names: frozenset) -> dict:
    return {
        "prefixed": set(names) if arm == "plugin" else set(),
        "plain": set(names) if arm == "skills" else set(names & CLI_BUNDLED_SKILLS),
        "plugin": arm == "plugin",
        "hook": arm != "bare",
    }


def auth_blocked(events: list) -> bool:
    return any(e.get("error") == "authentication_failed" for e in events if e.get("type") == "assistant")


def wiring_problems(arm: str, events: list, names: frozenset) -> list:
    """How one arm's init and hook events differ from its expected Consult wiring; empty when they match."""
    init = first_event(events, "system", "init")
    if init is None:
        return ["no init event"]
    seen = {**listed_consult(init, names), "hook": hook_fired(events)}
    want = expected_wiring(arm, names)
    problems = [f"{key}: expected {sorted_or(want[key])}, got {sorted_or(seen[key])}"
                for key in want if seen[key] != want[key]]
    return problems + ([] if auth_blocked(events) else ["the run did not stop at auth"])


def sorted_or(value) -> str:
    return (", ".join(sorted(value)) or "none") if isinstance(value, set) else str(value)


def wiring_row(case: Case, arm: str, run: RunConfig, names: frozenset, stamp: str) -> dict:
    container = f"{IMAGE_PREFIX}-wiring-{stamp}-{os.getpid()}-{case.name}-{arm}"
    argv = docker_argv(image_tag(case), container, arm, run, case.prompt, with_token=False)
    try:
        proc = subprocess.run(argv, capture_output=True, text=True, timeout=WIRING_TIMEOUT_SEC)
        events = parse_stream(proc.stdout.splitlines())
    except subprocess.TimeoutExpired:
        kill(container)
        events = []
    init = first_event(events, "system", "init") or {}
    listed = listed_consult(init, names)
    return {"case": case.name, "arm": arm, "prefixed": len(listed["prefixed"]), "plain": len(listed["plain"]),
            "plugin": listed["plugin"], "hook": hook_fired(events), "problems": wiring_problems(arm, events, names)}


def wiring_check(cases: list, arms: list, run: RunConfig, names: frozenset) -> int:
    build_images(cases)
    stamp = dt.datetime.now().strftime("%Y%m%dT%H%M%S")
    rows = [wiring_row(case, arm, run, names, stamp) for case, arm in product(cases, arms)]
    lines = ["| case | arm | consult:* listed | plain listed | plugin | hook | result |", "| --- | --- | ---: | ---: | --- | --- | --- |"]
    lines += [f"| {r['case']} | {r['arm']} | {r['prefixed']} | {r['plain']} | {r['plugin']} | {r['hook']} "
              f"| {'ok' if not r['problems'] else '; '.join(r['problems'])} |" for r in rows]
    print("\n".join(lines))
    return 1 if any(r["problems"] for r in rows) else 0


# ---------------------------------------------------------------------- cli

def agent_defaults() -> tuple:
    """Model (without the anthropic/ prefix), effort, and the consult-arm settings file from the Claude Code agent
    fragment, so the trigger suite and the Harbor arms run the same configuration."""
    import yaml

    agent = yaml.safe_load(AGENT_CONFIG.read_text())
    model = str(agent.get("model_name") or "")
    model = model[len("anthropic/"):] if model.startswith("anthropic/") else model
    effort = (agent.get("kwargs") or {}).get("reasoning_effort")
    return model, effort, REPO_DIR / agent["consult_settings"]


def select_cases(cases: tuple, patterns: Optional[str]) -> list:
    if not patterns:
        return list(cases)
    wanted = [p.strip() for p in patterns.split(",") if p.strip()]
    unmatched = [p for p in wanted if not any(fnmatch.fnmatchcase(c.name, p) for c in cases)]
    if unmatched:
        raise SystemExit(f"--cases matched nothing for {', '.join(unmatched)}")
    return [c for c in cases if any(fnmatch.fnmatchcase(c.name, p) for p in wanted)]


def parse_arms(value: str) -> list:
    arms = [a.strip() for a in value.split(",") if a.strip()]
    unknown = [a for a in arms if a not in ARMS]
    if unknown or not arms:
        raise SystemExit(f"--arms takes a comma-separated subset of {', '.join(ARMS)}; got {value!r}")
    return arms


def parse_args(argv: Optional[list] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--suite", type=Path, default=CASES_PATH, help="cases file (default: eval/triggers/cases.yaml)")
    parser.add_argument("--cases", help="comma-separated case names or globs (default: all)")
    parser.add_argument("--arms", default="plugin", help=f"comma-separated subset of {','.join(ARMS)}")
    parser.add_argument("--attempts", type=int, default=3)
    parser.add_argument("--concurrency", type=int, default=3)
    parser.add_argument("--model", help="default: model_name in eval/agents/claude-code.yaml")
    parser.add_argument("--effort", choices=EFFORTS,
                        help="passed as --effort (default: reasoning_effort in eval/agents/claude-code.yaml)")
    parser.add_argument("--plugin", type=Path, default=PLUGIN_DIR, help="plugin dir for the plugin arm")
    parser.add_argument("--max-turns", type=int, default=30)
    parser.add_argument("--max-budget-usd", type=float, default=3.0)
    parser.add_argument("--label", help="run dir suffix (default: the model, plus effort when given)")
    parser.add_argument("--dry-run", action="store_true", help="print the images and docker commands, run nothing")
    parser.add_argument("--wiring-check", action="store_true", help="check each arm's wiring without a model call")
    return parser.parse_args(argv)


def run_config(args: argparse.Namespace) -> RunConfig:
    model, effort, settings = agent_defaults()
    plugin_dir = args.plugin.resolve()
    if not (plugin_dir / "plugin.json").is_file() and not (plugin_dir / ".claude-plugin" / "plugin.json").is_file():
        raise SystemExit(f"--plugin {plugin_dir} has no plugin.json")
    return RunConfig(model=args.model or model, effort=args.effort or effort, max_turns=args.max_turns,
                     max_budget_usd=args.max_budget_usd, plugin_dir=plugin_dir, settings_file=settings)


def plan(cases: list, arms: list, attempts: int) -> list:
    return [Trial(case, arm, attempt, image_tag(case))
            for case, arm, attempt in product(cases, arms, range(1, attempts + 1))]


def dry_run(trials: list, run: RunConfig) -> int:
    for tag in dict.fromkeys(t.image for t in trials):
        print(f"build {tag}")
    for trial in trials:
        argv = docker_argv(trial.image, container_name("DRYRUN", trial), trial.arm, run, "<prompt>", with_token=True)
        stop = "stop at first write" if trial.case.kind == "positive" else "run to the end"
        print(f"\n# {trial.case.name} [{trial.arm} #{trial.attempt}, {stop}] prompt: {trial.case.prompt[:80]!r}")
        print(shlex.join(argv))
    return 0


def run_suite(suite: Suite, trials: list, arms: list, run: RunConfig, args: argparse.Namespace, names: frozenset) -> int:
    build_images(t.case for t in trials)
    stamp = dt.datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    label = args.label or run.model + (f"-{run.effort}" if run.effort else "")
    out_dir = RUNS_DIR / f"{stamp}-{label}"
    (out_dir / "transcripts").mkdir(parents=True)
    with ThreadPoolExecutor(max_workers=args.concurrency) as pool:
        records = list(pool.map(lambda t: run_trial(t, run, names, out_dir, stamp), trials))
    metrics = {arm: arm_metrics([r for r in records if r["arm"] == arm], suite.thresholds, suite.confidence)
               for arm in arms}
    results = {"run": {"label": label, "model": run.model, "effort": run.effort, "arms": arms,
                       "attempts": args.attempts, "max_turns": run.max_turns, "max_budget_usd": run.max_budget_usd,
                       "plugin_dir": str(run.plugin_dir)},
               "confidence": suite.confidence, "thresholds": suite.thresholds, "metrics": metrics, "trials": records}
    (out_dir / "results.json").write_text(json.dumps(results, indent=2))
    report = render_report(results)
    (out_dir / "report.md").write_text(report)
    print(f"\n{report}\n{out_dir}")
    return 0 if all(metrics[a]["overall"] == "pass" for a in arms if a in CONSULT_ARMS) else 1


def main(argv: Optional[list] = None) -> int:
    args = parse_args(argv)
    names = catalog()
    suite = load_suite(args.suite, names)
    cases = select_cases(suite.cases, args.cases)
    arms = parse_arms(args.arms)
    run = run_config(args)
    if args.dry_run:
        return dry_run(plan(cases, arms, args.attempts), run)
    if args.wiring_check:
        return wiring_check(cases, arms, run, names)
    if not os.environ.get("CLAUDE_CODE_OAUTH_TOKEN"):
        raise SystemExit("CLAUDE_CODE_OAUTH_TOKEN is not set. Run `claude setup-token` and export it; "
                         "--dry-run and --wiring-check need no token.")
    return run_suite(suite, plan(cases, arms, args.attempts), arms, run, args, names)


if __name__ == "__main__":
    raise SystemExit(main())
