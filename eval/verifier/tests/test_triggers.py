"""The trigger suite: transcript scoring, write detection, metrics, the cases file, and the CLI.

  python3 -m unittest discover eval/verifier/tests
"""

from __future__ import annotations

import io
import itertools
import json
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

EVAL_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(EVAL_DIR / "scripts"))

import triggers  # noqa: E402

try:
    import yaml
except ImportError:  # CI's unittest step is standard library only
    yaml = None

NAMES = triggers.catalog()
NEEDS_YAML = unittest.skipUnless(yaml, "pyyaml is not installed; run with uv run --project eval")
PLUGIN_SKILLS = ["deep-research", "code-review", *(f"consult:{n}" for n in sorted(NAMES))]
CALL_IDS = itertools.count()


def case(kind="positive", required=("debugging",), silent=("release",), code_change=True, name="c"):
    return triggers.Case(name=name, kind=kind, source_kind="task", source="bug-from-symptom", prompt="p",
                         code_change=code_change, required_any=tuple(required), expect_silent=tuple(silent))


def init(skills=PLUGIN_SKILLS, plugins=({"name": "consult"},), **extra):
    return {"type": "system", "subtype": "init", "model": "claude-opus-5-5", "skills": list(skills),
            "plugins": list(plugins), "claude_code_version": "2.1.282", **extra}


def call(name, **args):
    return {"type": "assistant", "parent_tool_use_id": None,
            "message": {"content": [{"type": "tool_use", "id": f"t{next(CALL_IDS)}", "name": name, "input": args}]}}


def failed(event, text="<tool_use_error>Unknown skill</tool_use_error>"):
    """The error tool_result Claude Code sends back for a call event."""
    use_id = event["message"]["content"][0]["id"]
    return {"type": "user", "parent_tool_use_id": None, "message": {"role": "user", "content": [
        {"type": "tool_result", "tool_use_id": use_id, "content": text, "is_error": True}]}}


def skill(name):
    return call("Skill", skill=name)


def write():
    return call("Edit", file_path="/app/src/store.js", old_string="a", new_string="b")


def result(subtype="success", cost=0.42, reason="completed"):
    return {"type": "result", "subtype": subtype, "total_cost_usd": cost, "duration_ms": 1200,
            "terminal_reason": reason, "num_turns": 3, "modelUsage": {"claude-opus-5-5": {}}}


def hook(output="Consult is installed. Before a non-trivial feature..."):
    return {"type": "system", "subtype": "hook_response", "hook_event": "SessionStart", "output": output}


def record(events, kase=None, arm="plugin", **kwargs):
    """Score events the way the runner does: through their stream-json text."""
    lines = [json.dumps(e) for e in events] + ["not json"]
    return triggers.trial_record(kase or case(), arm, 1, triggers.parse_stream(lines), NAMES, **kwargs)


class TranscriptScoringTests(unittest.TestCase):
    def test_a_skill_call_before_the_first_write_is_on_time(self):
        trial = record([init(), skill("consult:workflow"), skill("consult:debugging"), write(), result()])
        self.assertEqual([(l["skill"], l["on_time"]) for l in trial["loads"]], [("workflow", True), ("debugging", True)])
        self.assertTrue(trial["workflow_on_time"])
        self.assertTrue(trial["required_hit"])
        self.assertEqual(trial["first_write"], 2)

    def test_a_skill_call_after_the_first_write_does_not_count(self):
        trial = record([init(), write(), skill("consult:workflow"), skill("consult:debugging"), result()])
        self.assertEqual([l["on_time"] for l in trial["loads"]], [False, False])
        self.assertFalse(trial["workflow_on_time"])
        self.assertFalse(trial["required_hit"])

    def test_the_consult_prefix_is_optional(self):
        trial = record([init(skills=sorted(NAMES)), skill("workflow"), skill("/consult:debugging"), result()])
        self.assertEqual([l["skill"] for l in trial["loads"]], ["workflow", "debugging"])

    def test_a_skill_outside_the_catalog_is_ignored(self):
        trial = record([init(), skill("simplify"), skill("debug"), skill("consult:nonsense"), result()])
        self.assertEqual(trial["loads"], [])
        self.assertFalse(trial["any_load"])

    def test_a_plain_name_listed_beside_its_consult_twin_is_the_bundled_skill(self):
        trial = record([init(), skill("code-review"), skill("consult:code-review"), result()])
        self.assertEqual([l["call"] for l in trial["loads"]], [1])

    def test_the_clis_own_code_review_is_a_consult_load_only_in_the_skills_arm(self):
        negative = case(kind="negative", required=(), silent=())
        bare = record([init(skills=["deep-research", "code-review"], plugins=()), skill("code-review"), result()],
                      kase=negative, arm="bare")
        skills = record([init(skills=sorted(NAMES), plugins=()), skill("code-review"), result()],
                        kase=negative, arm="skills")
        self.assertFalse(bare["any_load"])
        self.assertTrue(skills["any_load"])

    def test_a_call_whose_result_is_an_error_loads_nothing(self):
        rejected = skill("consult:workflow")
        missing = call("Read", file_path="/logs/agent/sessions/skills/workfow/SKILL.md")
        trial = record([init(skills=sorted(NAMES), plugins=()), rejected, failed(rejected), missing,
                        failed(missing, "File does not exist."), skill("workflow"), result()], arm="skills")
        self.assertEqual([(l["skill"], l["call"]) for l in trial["loads"]], [("workflow", 2)])

    def test_reading_a_skill_md_counts_as_a_load(self):
        trial = record([init(), call("Read", file_path="/opt/consult-plugin/skills/workflow/SKILL.md"),
                        call("Bash", command="cat /logs/agent/sessions/skills/debugging/SKILL.md"),
                        call("Read", file_path="/app/skills/unknown/SKILL.md"), result()])
        self.assertEqual([l["skill"] for l in trial["loads"]], ["workflow", "debugging"])

    def test_a_bash_write_ends_the_on_time_window(self):
        trial = record([init(), call("Bash", command="npm test"), call("Bash", command="sed -i 's/a/b/' src/x.js"),
                        skill("consult:debugging"), result()])
        self.assertEqual(trial["first_write"], 1)
        self.assertFalse(trial["required_hit"])

    def test_a_negative_counts_any_load_even_after_writes(self):
        negative = case(kind="negative", required=(), silent=())
        trial = record([init(), write(), skill("consult:workflow"), result()], kase=negative)
        self.assertTrue(trial["any_load"])

    def test_off_target_lists_expect_silent_loads(self):
        trial = record([init(), skill("consult:release"), skill("consult:debugging"), result()])
        self.assertEqual(trial["off_target"], ["release"])

    def test_the_record_keeps_run_facts_and_the_hook(self):
        trial = record([hook(), init(per_turn_effort_active=True), result("error_max_budget_usd", 3.01)])
        self.assertEqual(trial["result_subtype"], "error_max_budget_usd")
        self.assertEqual(trial["cost_usd"], 3.01)
        self.assertEqual(trial["model"], "claude-opus-5-5")
        self.assertEqual(trial["effort_evidence"], {"per_turn_effort_active": True})
        self.assertTrue(trial["hook_fired"])
        self.assertEqual(trial["outcome"], "completed")

    def test_outcomes(self):
        self.assertEqual(record([init(), write()], stopped=True)["outcome"], "stopped_at_write")
        self.assertEqual(record([init(), skill("consult:workflow")], timed_out=True)["outcome"], "timed_out")
        self.assertEqual(record([init(), result(reason="api_error")])["outcome"], "error")
        self.assertEqual(record([])["outcome"], "error")


class BashWriteTests(unittest.TestCase):
    WRITES = [
        "echo hi > src/a.js", "cat >> notes.md <<'EOF'\nhi\nEOF", "sed -i 's/a/b/' src/a.js", "sed -i.bak -e x f",
        "mv a b", "cp a b", "rm -f a", "/bin/rm a", "git add -A && git commit -m 'split'", "git -C /app commit",
        "npm install left-pad", "npm i", "ls | tee out.txt", "cd /app && FOO=1 rm x", "printf x >out",
        "npm test 2>err.log", "node --test 1>out.txt", "npm test &>log.txt", "npm test 2>> err.log",
        "npm version 2.0.0 --no-git-tag-version", "npm pkg set scripts.lint=eslint", "mkdir -p .github/workflows",
        "git mv a b", "git rm old.js", "npx prettier --write .",
        "node -e \"require('fs').writeFileSync('x', '')\"",
        # Opus 5.5 edited src/orders.js this way in the first calibration run.
        "python3 - <<'EOF'\np='src/orders.js'; s=open(p).read()\nopen(p,'w').write(s)\nEOF",
        "python3 -c \"from pathlib import Path; Path('a').write_text('x')\"", "perl -pi -e 's/a/b/' src/a.js",
    ]
    READS = [
        "npm test 2>&1", "node --test > /dev/null", "npm test 2>/dev/null", "ls >&2", "grep -rn 'a > b' src",
        'echo "x > y"', "cat src/a.js", "git status && git diff", "git log --oneline", "sed -n 1,20p src/a.js",
        "npm test", "node -e 'a => a'", "[ $a -ge 1 ]", "npm test &>/dev/null", "echo x 1>&2",
        "npm version", "npm version --json", "npm pkg get version", "npx prettier --check .",
        "python3 -c \"print(open('src/a.js').read())\"", "node -e \"console.log(require('fs').readFileSync('x'))\"",
        "python3 - <<'EOF'\nimport json; print(json.load(open('package.json')))\nEOF",
        "node -e \"process.stdout.write('x')\"",
    ]

    def test_commands_that_clearly_write(self):
        for command in self.WRITES:
            with self.subTest(command=command):
                self.assertTrue(triggers.bash_writes(command))

    def test_commands_that_do_not_write(self):
        for command in self.READS:
            with self.subTest(command=command):
                self.assertFalse(triggers.bash_writes(command))


class StreamTests(unittest.TestCase):
    def test_a_positive_stream_kills_the_container_at_the_first_write(self):
        lines = [json.dumps(e) + "\n" for e in (init(), skill("consult:workflow"), write(), write())]
        out = io.StringIO()
        with mock.patch.object(triggers, "kill") as kill:
            events, stopped = triggers.pump(iter(lines), out, "box", stop_at_write=True)
        kill.assert_called_once_with("box")
        self.assertTrue(stopped)
        self.assertEqual(out.getvalue(), "".join(lines))
        self.assertEqual(len(events), 4)

    def test_a_negative_stream_runs_to_the_end(self):
        lines = [json.dumps(e) + "\n" for e in (init(), write(), result())]
        with mock.patch.object(triggers, "kill") as kill:
            _, stopped = triggers.pump(iter(lines), io.StringIO(), "box", stop_at_write=False)
        kill.assert_not_called()
        self.assertFalse(stopped)

    def test_a_trial_past_its_timeout_is_killed_and_marked_timed_out(self):
        child = f"import time; print({json.dumps(json.dumps(init()))}, flush=True); time.sleep(30)"
        procs, popen = [], subprocess.Popen

        def start(*args, **kwargs):
            procs.append(popen(*args, **kwargs))
            return procs[-1]

        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(triggers, "TRIAL_TIMEOUT_SEC", 0.5):
            with mock.patch.object(triggers.subprocess, "Popen", side_effect=start), \
                    mock.patch.object(triggers, "kill", side_effect=lambda _: procs[0].kill()) as kill:
                events, stopped, timed_out = triggers.stream_container(
                    [sys.executable, "-c", child], "box", Path(tmp) / "t.jsonl", stop_at_write=True)
        procs[0].stdout.close()
        kill.assert_called_once_with("box")
        self.assertTrue(timed_out)
        self.assertFalse(stopped)
        self.assertEqual([e.get("subtype") for e in events], ["init"])


THRESHOLDS = {"workflow_recall": {"min": 0.83}, "narrow_recall": {"min": 0.73},
              "false_trigger_rate": {"max": 0.08}, "negative_case_max_triggered": 1}


def positive_trial(loads, name="p", **kwargs):
    return record([init(), *map(skill, loads), write(), result()], kase=case(name=name, **kwargs))


def negative_trial(loads, name="n", reason="completed", **kwargs):
    kase = case(kind="negative", required=(), name=name)
    return record([init(), *map(skill, loads), result(reason=reason)], kase=kase, **kwargs)


def report_for(trials):
    results = {"run": {"label": "t", "model": "m", "effort": None, "arms": ["plugin"], "attempts": 2,
                       "max_turns": 30, "max_budget_usd": 3.0},
               "confidence": 0.9, "trials": trials,
               "metrics": {"plugin": triggers.arm_metrics(trials, THRESHOLDS, 0.9)}}
    return triggers.render_report(results)


class MetricsTests(unittest.TestCase):
    def test_wilson_interval_matches_the_reference(self):
        low, high = triggers.wilson(8, 10, 0.90)
        self.assertAlmostEqual(low, 0.5408, places=4)
        self.assertAlmostEqual(high, 0.9314, places=4)
        self.assertEqual(triggers.wilson(0, 24, 0.90)[0], 0.0)
        self.assertIsNone(triggers.wilson(0, 0, 0.90))

    def test_an_arm_that_meets_every_threshold_passes(self):
        trials = [positive_trial(["consult:workflow", "consult:debugging"]) for _ in range(6)]
        trials += [negative_trial([], name=f"n{i}") for i in range(12)]
        metrics = triggers.arm_metrics(trials, THRESHOLDS, 0.90)
        self.assertEqual([metrics[m]["verdict"] for m in triggers.METRICS], ["pass", "pass", "pass"])
        self.assertEqual(metrics["overall"], "pass")

    def test_recall_below_its_threshold_fails(self):
        trials = [positive_trial(["consult:workflow", "consult:debugging"]) for _ in range(4)]
        trials += [positive_trial([]), negative_trial([])]
        metrics = triggers.arm_metrics(trials, THRESHOLDS, 0.90)
        self.assertEqual((metrics["workflow_recall"]["hits"], metrics["workflow_recall"]["n"]), (4, 5))
        self.assertEqual(metrics["workflow_recall"]["verdict"], "fail")
        self.assertEqual(metrics["overall"], "fail")

    def test_workflow_recall_counts_only_code_changing_positives(self):
        trials = [positive_trial(["consult:workflow", "consult:debugging"]),
                  positive_trial(["consult:commit"], required=("commit",), code_change=False)]
        metrics = triggers.arm_metrics(trials, THRESHOLDS, 0.90)
        self.assertEqual(metrics["workflow_recall"]["n"], 1)
        self.assertEqual(metrics["narrow_recall"]["hits"], 2)

    def test_a_negative_that_triggers_in_two_attempts_fails_the_arm(self):
        trials = [negative_trial([], name=f"quiet{i}") for i in range(30)]
        trials += [negative_trial(["consult:workflow"], name="loud"), negative_trial(["consult:workflow"], name="loud")]
        trials += [positive_trial(["consult:workflow", "consult:debugging"])]
        metrics = triggers.arm_metrics(trials, THRESHOLDS, 0.90)
        self.assertEqual(metrics["false_trigger_rate"]["verdict"], "pass")
        self.assertEqual(metrics["failing_negative_cases"], ["loud"])
        self.assertEqual(metrics["overall"], "fail")

    def test_error_trials_are_excluded_and_counted(self):
        trials = [positive_trial(["consult:workflow", "consult:debugging"]), record([]), negative_trial([])]
        metrics = triggers.arm_metrics(trials, THRESHOLDS, 0.90)
        self.assertEqual(metrics["errors"], 1)
        self.assertEqual(metrics["narrow_recall"]["n"], 1)

    def test_a_negative_that_loads_before_an_api_error_still_counts(self):
        errored = [negative_trial(["consult:workflow"], name="run-tests", reason="api_error") for _ in range(2)]
        trials = errored + [negative_trial([], name=f"quiet{i}") for i in range(10)]
        trials += [positive_trial(["consult:workflow", "consult:debugging"]) for _ in range(6)]
        metrics = triggers.arm_metrics(trials, THRESHOLDS, 0.90)
        self.assertEqual([t["outcome"] for t in errored], ["error", "error"])
        self.assertEqual((metrics["false_trigger_rate"]["hits"], metrics["false_trigger_rate"]["n"]), (2, 12))
        self.assertEqual(metrics["failing_negative_cases"], ["run-tests"])
        self.assertEqual(metrics["overall"], "fail")
        self.assertIn("| run-tests | negative | 2 | - | - | 2/2 | error after workflow / error after workflow |",
                      report_for(errored))

    def test_a_pass_says_whether_the_interval_meets_the_threshold(self):
        trials = [negative_trial([], name=f"quiet{i}") for i in range(23)] + [negative_trial(["consult:workflow"])]
        self.assertIn("| false_trigger_rate | 1/24 | 4% | 1% to 17% | <= 8% | pass | no |", report_for(trials))

    def test_an_arm_with_no_negatives_is_incomplete(self):
        metrics = triggers.arm_metrics([positive_trial(["consult:workflow", "consult:debugging"])], THRESHOLDS, 0.90)
        self.assertEqual(metrics["false_trigger_rate"]["verdict"], "no data")
        self.assertEqual(metrics["overall"], "incomplete")

    def test_the_report_has_a_row_per_case_with_loads_in_order(self):
        trials = [positive_trial(["consult:workflow", "consult:debugging"], name="bug"),
                  record([init(), write(), skill("consult:debugging"), result()], kase=case(name="bug")),
                  negative_trial(["consult:workflow"], name="typo")]
        for attempt, trial in enumerate(trials[:2], start=1):
            trial["attempt"] = attempt
        report = report_for(trials)
        self.assertIn("| bug | positive | 2 | 1/2 | 1/2 | - | workflow > debugging / debugging* |", report)
        self.assertIn("| typo | negative | 1 | - | - | 1/1 | workflow |", report)
        self.assertIn("| false_trigger_rate | 1/1 | 100% |", report)


class WiringTests(unittest.TestCase):
    AUTH_FAIL = {"type": "assistant", "error": "authentication_failed", "message": {"content": []}}

    def test_each_arm_matches_its_expected_wiring(self):
        skills_arm = init(skills=[*sorted(NAMES), "deep-research"], plugins=())
        bare = init(skills=["deep-research", "code-review"], plugins=())
        self.assertEqual(triggers.wiring_problems("plugin", [hook(), init(), self.AUTH_FAIL], NAMES), [])
        self.assertEqual(triggers.wiring_problems("skills", [hook(), skills_arm, self.AUTH_FAIL], NAMES), [])
        self.assertEqual(triggers.wiring_problems("bare", [bare, self.AUTH_FAIL], NAMES), [])

    def test_a_mismatch_is_reported(self):
        problems = triggers.wiring_problems("bare", [hook(), init(), self.AUTH_FAIL], NAMES)
        self.assertTrue(any(p.startswith("prefixed:") for p in problems))
        self.assertTrue(any(p.startswith("hook:") for p in problems))
        self.assertEqual(triggers.wiring_problems("skills", [], NAMES), ["no init event"])
        self.assertIn("the run did not stop at auth", triggers.wiring_problems("plugin", [hook(), init()], NAMES))


@NEEDS_YAML
class CasesFileTests(unittest.TestCase):
    def setUp(self) -> None:
        self.doc = yaml.safe_load(triggers.CASES_PATH.read_text())

    def test_the_cases_file_is_valid(self):
        self.assertEqual(triggers.suite_problems(self.doc, NAMES), [])
        kinds = [c["kind"] for c in self.doc["cases"]]
        self.assertEqual(kinds.count("negative"), 8)

    def test_task_positives_carry_the_tasks_expect_silent(self):
        for raw in self.doc["cases"]:
            task = raw["source"].get("task")
            meta_path = EVAL_DIR / "tasks" / str(task) / "tests" / "consult.json"
            if raw["kind"] != "positive" or not meta_path.is_file():
                continue
            with self.subTest(case=raw["name"]):
                silent = json.loads(meta_path.read_text()).get("expect_silent") or []
                self.assertLessEqual(set(silent), set(raw["expect_silent"]))

    def test_unknown_tasks_skills_and_stale_edits_are_reported(self):
        bad = [
            {"name": "a", "kind": "positive", "source": {"task": "no-such-task"}, "code_change": True, "required_any": ["debugging"]},
            {"name": "b", "kind": "positive", "source": {"task": "bug-from-symptom"}, "code_change": True, "required_any": ["debuging"]},
            {"name": "c", "kind": "negative", "source": {"task": "bug-from-symptom"}, "code_change": False,
             "edits": [{"path": "src/store.js", "replace": ["not in the file", "x"]}]},
            {"name": "d", "kind": "negative", "source": {"fixture": "slow-report"}, "code_change": False},
        ]
        problems = triggers.suite_problems({**self.doc, "cases": bad}, NAMES)
        self.assertEqual([p.split(":")[0] for p in problems], ["a", "b", "c", "d"])
        self.assertIn("no eval task", problems[0])
        self.assertIn("unknown skill 'debuging'", problems[1])
        self.assertIn("found it 0 times", problems[2])
        self.assertIn("needs a prompt", problems[3])

    def test_a_multi_step_task_prompts_with_its_first_step(self):
        suite = triggers.load_suite(names=NAMES)
        money = next(c for c in suite.cases if c.name == "money-field-change")
        brief = EVAL_DIR / "tasks" / "money-field-change" / "steps" / "brief" / "instruction.md"
        self.assertEqual(money.prompt, brief.read_text().strip())

    def test_edits_land_before_the_scaffold_commit_and_uncommitted_after(self):
        suite = triggers.load_suite(names=NAMES)
        by_name = {c.name: c for c in suite.cases}
        with tempfile.TemporaryDirectory() as tmp:
            typo = triggers.materialize(by_name["readme-typo"], Path(tmp) / "typo")
            dirty = triggers.materialize(by_name["commit-dirty-tree"], Path(tmp) / "dirty")
            self.assertIn("storefornt", (typo / "workspace" / "README.md").read_text())
            self.assertFalse((typo / "uncommitted").exists())
            self.assertIn("welcome email", (dirty / "workspace" / "README.md").read_text())
            self.assertIn("farewells", (dirty / "uncommitted" / "README.md").read_text())
            self.assertTrue((dirty / "Dockerfile").read_text().rstrip().endswith("COPY uncommitted/ /app/"))


@NEEDS_YAML
class CliTests(unittest.TestCase):
    def run_main(self, argv, env):
        out = io.StringIO()
        with mock.patch.dict(os.environ, env, clear=True), redirect_stdout(out):
            code = triggers.main(argv)
        return code, out.getvalue()

    def test_dry_run_passes_the_token_by_name_only(self):
        code, out = self.run_main(["--dry-run", "--cases", "bug-from-symptom", "--arms", "plugin,skills,bare",
                                   "--attempts", "1"], {"CLAUDE_CODE_OAUTH_TOKEN": "secret-token-value"})
        self.assertEqual(code, 0)
        self.assertNotIn("secret-token-value", out)
        self.assertEqual(out.count("-e CLAUDE_CODE_OAUTH_TOKEN "), 3)
        self.assertIn("--plugin-dir /opt/consult-plugin", out)
        self.assertIn("--settings /tmp/claude-code-settings/settings.json", out)
        self.assertNotIn(str(Path.home() / ".claude"), out)

    def test_the_effort_defaults_to_the_agent_fragment_and_the_flag_overrides_it(self):
        with tempfile.TemporaryDirectory() as tmp:
            fragment = Path(tmp) / "claude-code.yaml"
            fragment.write_text("model_name: anthropic/claude-opus-5-5\nconsult_settings: plugin/hooks/hooks.json\n"
                                "kwargs:\n  reasoning_effort: high\n")
            argv = ["--dry-run", "--cases", "bug-from-symptom", "--arms", "plugin", "--attempts", "1"]
            with mock.patch.object(triggers, "AGENT_CONFIG", fragment):
                _, default = self.run_main(argv, {})
                _, override = self.run_main([*argv, "--effort", "medium"], {})
        self.assertIn("--effort high", default)
        self.assertIn("--effort medium", override)
        self.assertNotIn("--effort high", override)

    def test_a_run_without_a_token_fails_before_docker(self):
        with mock.patch.object(triggers, "build_images") as build:
            with self.assertRaises(SystemExit) as raised:
                self.run_main(["--cases", "bug-from-symptom"], {})
        build.assert_not_called()
        self.assertIn("CLAUDE_CODE_OAUTH_TOKEN is not set", str(raised.exception))

    def test_suite_selects_another_cases_file(self):
        doc = yaml.safe_load(triggers.CASES_PATH.read_text())
        doc["cases"] = [{**next(c for c in doc["cases"] if c["name"] == "readme-typo"), "name": "other-file-case"}]
        with tempfile.TemporaryDirectory() as tmp:
            other = Path(tmp) / "other.yaml"
            other.write_text(yaml.safe_dump(doc))
            code, out = self.run_main(["--dry-run", "--suite", str(other), "--attempts", "1"], {})
        self.assertEqual(code, 0)
        self.assertIn("other-file-case", out)
        self.assertNotIn("bug-from-symptom", out)

    def test_cases_that_match_nothing_are_an_error(self):
        with self.assertRaises(SystemExit) as raised:
            self.run_main(["--dry-run", "--cases", "bug-from-symptom,no-such-*"], {})
        self.assertEqual(str(raised.exception), "--cases matched nothing for no-such-*")


@NEEDS_YAML
class RunSuiteTests(unittest.TestCase):
    """main with Docker stubbed: bug-from-symptom (positive) and readme-typo (negative), one attempt per arm."""

    # Events per arm outcome, keyed by whether the case is a positive.
    GOOD = {True: [init(), skill("consult:workflow"), skill("consult:debugging"), write()], False: [init(), result()]}
    MISSED = {True: [init(), write()], False: [init(), result()]}
    ERRORED = {True: [init(), result(reason="api_error")], False: [init(), result(reason="api_error")]}

    def run_suite(self, events_by_arm):
        def stream(argv, container, transcript, stop_at_write):
            events = events_by_arm[transcript.stem.split("__")[1]][stop_at_write]
            stopped = stop_at_write and any(map(triggers.is_write_call, triggers.tool_calls(events)))
            return events, stopped, False

        argv = ["--cases", "bug-from-symptom,readme-typo", "--arms", ",".join(events_by_arm), "--attempts", "1"]
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(triggers, "RUNS_DIR", Path(tmp)):
            with mock.patch.object(triggers, "build_images"), \
                    mock.patch.object(triggers, "stream_container", side_effect=stream), \
                    mock.patch.dict(os.environ, {"CLAUDE_CODE_OAUTH_TOKEN": "t"}, clear=True), \
                    redirect_stdout(io.StringIO()):
                code = triggers.main(argv)
            run_dir = next(Path(tmp).iterdir())
            return code, json.loads((run_dir / "results.json").read_text()), (run_dir / "report.md").read_text()

    def test_a_passing_run_writes_results_and_a_report_and_exits_0(self):
        code, results, report = self.run_suite({"plugin": self.GOOD})
        self.assertEqual(code, 0)
        self.assertEqual(results["metrics"]["plugin"]["overall"], "pass")
        self.assertEqual(len(results["trials"]), 2)
        self.assertIn("Overall: **pass**", report)

    def test_a_failing_consult_arm_exits_1(self):
        code, results, _ = self.run_suite({"plugin": self.MISSED})
        self.assertEqual(results["metrics"]["plugin"]["overall"], "fail")
        self.assertEqual(code, 1)

    def test_a_failing_bare_arm_does_not_fail_the_run(self):
        code, results, _ = self.run_suite({"plugin": self.GOOD, "bare": self.MISSED})
        self.assertEqual(results["metrics"]["bare"]["overall"], "fail")
        self.assertEqual(code, 0)

    def test_a_run_with_no_usable_data_exits_1(self):
        code, results, _ = self.run_suite({"plugin": self.ERRORED})
        self.assertEqual(results["metrics"]["plugin"]["overall"], "incomplete")
        self.assertEqual(results["metrics"]["plugin"]["errors"], 2)
        self.assertEqual(code, 1)


@NEEDS_YAML
class WiringCheckCliTests(unittest.TestCase):
    PLUGIN_EVENTS = [hook(), init(), WiringTests.AUTH_FAIL]

    def wiring_check(self, arm):
        stdout = "".join(json.dumps(e) + "\n" for e in self.PLUGIN_EVENTS)
        done = subprocess.CompletedProcess([], 1, stdout=stdout, stderr="")
        with mock.patch.object(triggers, "build_images"), \
                mock.patch.object(triggers.subprocess, "run", return_value=done), \
                mock.patch.dict(os.environ, {}, clear=True), redirect_stdout(io.StringIO()) as out:
            code = triggers.main(["--wiring-check", "--cases", "bug-from-symptom", "--arms", arm])
        return code, out.getvalue()

    def test_matching_wiring_exits_0(self):
        code, out = self.wiring_check("plugin")
        self.assertEqual(code, 0)
        self.assertIn("| ok |", out)

    def test_a_wiring_mismatch_exits_1(self):
        code, out = self.wiring_check("bare")
        self.assertEqual(code, 1)
        self.assertIn("hook: expected False, got True", out)


if __name__ == "__main__":
    unittest.main()
