"""The activity breakdown: which kind of tool call each step's time and tokens go to, and words per stop.

python3 -m unittest discover eval/verifier/tests
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path

EVAL_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(EVAL_DIR / "scripts"))

import activity
import consult_lib as cl

T0 = datetime(2026, 11, 4, 12, 0, 0, tzinfo=UTC)
SKILL_BODY = "Base directory for this skill: /logs/agent/sessions/skills/proof\n\n# Proof\n"


def at(second: int) -> str:
    return (T0 + timedelta(seconds=second)).isoformat().replace("+00:00", "Z")


def user(second: int, message: str) -> dict:
    return {"source": "user", "message": message, "timestamp": at(second)}


def agent(second: int, *calls: tuple[str, dict], message: str = "", tokens: int = 0) -> dict:
    tool_calls = [
        {"tool_call_id": f"call_{second}_{i}", "function_name": name, "arguments": args}
        for i, (name, args) in enumerate(calls)
    ]
    return {
        "source": "agent",
        "message": message,
        "timestamp": at(second),
        "metrics": {"completion_tokens": tokens},
        "tool_calls": tool_calls,
    }


def bash(command: str) -> tuple[str, dict]:
    return ("Bash", {"command": command})


def write(path: str) -> tuple[str, dict]:
    return ("Write", {"file_path": path, "content": "export {};\n"})


class ActivityTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def trajectory(self, *steps: dict) -> cl.Trajectory:
        path = self.root / "trajectory.json"
        path.write_text(json.dumps({"steps": list(steps)}))
        return cl.load_trajectory(path)

    def category(self, call: tuple[str, dict]) -> str:
        return activity.call_category(self.trajectory(agent(0, call)).calls[0])

    def test_each_kind_of_call_gets_its_category(self):
        cases = [
            (bash("node --test src/orders/api.test.ts"), "test_targeted"),
            (bash("npm test 2>&1 | tail -5"), "test_suite"),
            (bash("npm run typecheck"), "static"),
            (bash("cd /app && sed -n 1,40p src/orders/order.ts"), "read"),
            (("Read", {"file_path": "/app/src/orders/order.ts"}), "read"),
            (write("/app/src/orders/api.test.ts"), "write_test"),
            (write("/app/openapi.yaml"), "write_spec"),
            (write("/app/src/orders/order.ts"), "write_other"),
            (bash("git status --short"), "git"),
            (("Skill", {"skill": "consult:proof"}), "skill"),
            (("Agent", {"prompt": "Review the diff."}), "subagent"),
            (("WebFetch", {"url": "https://nodejs.org/api/sqlite.html"}), "other"),
        ]
        for call, expected in cases:
            with self.subTest(call=call):
                self.assertEqual(self.category(call), expected)

    def test_a_break_and_restore_script_gets_its_own_category(self):
        script = (
            "cp src/a.ts /tmp/a.ts && sed -i 's/>=/>/' src/a.ts && node --test src/a.test.ts; cp /tmp/a.ts src/a.ts"
        )
        self.assertEqual(self.category(bash(script)), "break_restore")

    def test_a_script_that_edits_then_runs_the_tests_is_an_edit_and_test_script(self):
        script = (
            "python3 - <<'EOF'\np='src/commissions/commission.ts'\ns=open(p).read()\n"
            "open(p,'w').write(s.replace('a','b'))\nEOF\nnode --test src/commissions/commission.test.ts 2>&1 | tail -5"
        )
        self.assertEqual(self.category(bash(script)), "edit_test")

    def test_a_shell_edit_is_a_write_even_when_it_also_runs_a_static_check(self):
        edit = "python3 - <<'EOF'\np='src/http.ts'\ns=open(p).read()\nopen(p,'w').write(s)\nEOF\nnpx tsc --noEmit"
        append = "cat >> src/commissions/store.test.ts <<'EOF'\ntest('x', () => {});\nEOF"
        self.assertEqual(self.category(bash(edit)), "write_other")
        self.assertEqual(self.category(bash(append)), "write_test")

    def test_a_scratch_probe_outside_the_repo_is_not_a_read(self):
        probe = "cat > /tmp/probe.mjs <<'EOF'\nconsole.log(1);\nEOF\nnode /tmp/probe.mjs"
        self.assertEqual(self.category(bash(probe)), "other")
        self.assertEqual(self.category(bash(f"cd /tmp && {probe}")), "other")

    def test_a_test_path_outside_the_test_command_does_not_make_the_run_targeted(self):
        cases = [
            "sed -n 1,12p src/a.test.ts; npm test 2>&1 | tail -5",
            "git add src/rates/refresh.test.ts && npm test",
            "npm test 2>&1 | tail -3; npx tsc --noEmit test/*.ts",
            "npm test 2>&1 | grep -E 'src/a.test.ts|# fail'",
            "cat > /tmp/notes.txt <<'EOF'\nsee /app/src/app.test.ts\nEOF\nnpm test",
        ]
        for command in cases:
            with self.subTest(command=command):
                self.assertEqual(self.category(bash(command)), "test_suite")
        self.assertEqual(self.category(bash("cd /app && node --test src/a.test.ts 2>&1 | tail")), "test_targeted")
        self.assertEqual(self.category(bash('npm test -- --test-name-pattern="refund"')), "test_targeted")

    def test_a_test_command_in_quotes_or_a_heredoc_is_not_a_run(self):
        grep = 'ps -eo pid,args | grep -E "node .*src/main.ts|node --test" | grep -v grep'
        readme = "cat > README.md <<'EOF'\n# Shop\n\n    npm test\nEOF"
        commit = 'git commit -q -m "Run the API tests with node --test src/api.test.ts"'
        self.assertEqual(self.category(bash(grep)), "other")
        self.assertEqual(self.category(bash(readme)), "write_other")
        self.assertEqual(self.category(bash(commit)), "git")

    def test_a_test_run_in_a_command_substitution_inside_double_quotes_still_counts(self):
        script = "cd /tmp/mut && echo \"fails: $(node --test 2>&1 | grep -E '^# (fail|cancelled)')\""
        self.assertEqual(self.category(bash(script)), "test_suite")
        nested = 'H="$(curl -s -d "{}" localhost:3000/a)"; npm test 2>&1 | tail -3'
        self.assertEqual(self.category(bash(nested)), "test_suite")

    def test_an_apostrophe_in_a_comment_does_not_hide_the_commands_after_it(self):
        script = (
            "# Break 9: shown prices come from today's catalogue\nnode --test src/a.test.ts 2>&1 | grep -E '^# fail'"
        )
        self.assertEqual(self.category(bash(script)), "test_targeted")

    def test_a_script_written_in_the_call_and_then_run_counts_as_its_writes(self):
        edit = (
            "cat > /tmp/edit.mjs <<'EOF'\nimport { readFileSync, writeFileSync } from \"node:fs\";\n"
            'const path = "/app/src/commissions.ts";\nwriteFileSync(path, readFileSync(path, "utf8"));\nEOF\n'
            "node /tmp/edit.mjs; git diff --stat"
        )
        self.assertEqual(self.category(bash(edit)), "write_other")
        self.assertEqual(self.category(bash(edit + "; node --test src/commissions.test.ts")), "edit_test")
        probe = "cat > /tmp/probe.mjs <<'EOF'\nwriteFileSync('/tmp/out.json', '{}');\nEOF\nnode /tmp/probe.mjs"
        self.assertEqual(self.category(bash(probe)), "other")

    def test_a_mutation_script_written_in_the_call_is_a_break_and_restore_script(self):
        node = (
            'cat > /tmp/mutate.mjs <<\'EOF\'\nconst f = "/app/src/a.ts";\ncopyFileSync(f, f + ".orig");\n'
            "writeFileSync(f, src.replace(from, to));\n"
            'try { execSync("npm test 2>&1", { cwd: "/app" }); } finally { copyFileSync(f + ".orig", f); }\n'
            "EOF\nnode /tmp/mutate.mjs; git status --short"
        )
        shell = (
            "cat > /tmp/mutate.sh <<'EOF'\n# Break each rule, run the tests, put the file back.\n"
            "cp src/a.ts /tmp/a.ts\nsed -i 's/>=/>/' src/a.ts\nnpm test 2>&1 | tail -3\ncp /tmp/a.ts src/a.ts\n"
            "EOF\nbash /tmp/mutate.sh"
        )
        self.assertEqual(self.category(bash(node)), "break_restore")
        self.assertEqual(self.category(bash(shell)), "break_restore")

    def test_a_status_check_after_a_read_or_a_server_check_is_not_a_git_call(self):
        cases = [
            ("sed -n 1,70p src/http.ts; git status --short", "read"),
            ('curl -s localhost:3921/health || echo "stopped"; rm -f /tmp/smoke.db*; git status --short', "other"),
            ('for f in src/*.ts; do echo "=== $f"; cat -n $f; done; node --version', "read"),
            ("npx --yes @redocly/cli@2 lint openapi.yaml 2>&1 | tail -30", "static"),
            ("git log --oneline | head -5", "git"),
            ('ls src; G="git -c user.name=eval"; $G commit -q -m "Add refunds"', "git"),
        ]
        for command, expected in cases:
            with self.subTest(command=command):
                self.assertEqual(self.category(bash(command)), expected)

    def test_reading_a_skill_reference_counts_with_skill_loads(self):
        reference = "/logs/agent/sessions/skills/domain-modeling/references/money.md"
        self.assertEqual(self.category(bash(f"cat {reference}")), "skill")
        self.assertEqual(self.category(("Read", {"file_path": reference})), "skill")

    def test_time_and_tokens_go_to_the_step_that_made_the_call_and_waiting_on_a_prompt_does_not_count(self):
        trajectory = self.trajectory(
            user(0, "# Orders\n\nBuild it."),
            agent(10, bash("npm test"), tokens=100),
            agent(70, write("/app/src/orders/order.ts"), tokens=400),
            agent(80, message="Built it. Approve?", tokens=50),
            user(900, "Approved. Continue."),
            agent(905, bash("npm run typecheck"), tokens=20),
            agent(925, message="Done.", tokens=10),
        )
        totals = activity.trial_activity(trajectory)
        self.assertEqual(totals["test_suite"]["seconds"], 70.0)
        self.assertEqual(totals["write_other"]["seconds"], 10.0)
        self.assertEqual(totals["static"]["seconds"], 25.0)
        self.assertEqual(totals["message"]["seconds"], 0.0)
        self.assertEqual(totals["write_other"]["output_tokens"], 400.0)
        self.assertEqual(totals["message"]["calls"], 2.0)

    def test_a_skill_body_is_not_a_prompt_so_its_gap_counts_as_work(self):
        trajectory = self.trajectory(
            user(0, "Fix the bug."),
            agent(5, ("Skill", {"skill": "consult:proof"})),
            user(6, SKILL_BODY),
            agent(30, bash("node --test test/a.test.js")),
            agent(40, message="Fixed."),
        )
        totals = activity.trial_activity(trajectory)
        self.assertEqual(totals["skill"]["seconds"], 30.0)
        self.assertEqual(totals["test_targeted"]["seconds"], 10.0)

    def test_a_background_task_notice_is_not_a_prompt_so_waiting_for_it_counts_as_work(self):
        notice = "<task-notification>\n<task-id>a7b1ab3eb913674d4</task-id>\n<status>completed</status>"
        self.assertFalse(activity.is_prompt(user(0, notice)))
        trajectory = self.trajectory(
            user(0, "Build it."),
            agent(5, bash("npm test")),
            agent(10, message="Waiting for the test agent."),
            user(70, notice),
            agent(75, message="Done."),
        )
        self.assertEqual(activity.trial_activity(trajectory)["message"]["seconds"], 65.0)
        self.assertEqual(activity.words_per_stop(trajectory), 1.0)

    def test_a_subagents_opening_prompt_is_not_a_prompt_so_its_time_counts_as_work(self):
        trajectory = self.trajectory(
            user(0, "Build it."),
            agent(5, ("Agent", {"prompt": "Review the diff."})),
            {**user(6, "Review the diff."), "extra": {"is_sidechain": True}},
            {**agent(20, message="Looks right."), "extra": {"is_sidechain": True}},
            agent(30, message="Done."),
        )
        totals = activity.trial_activity(trajectory)
        self.assertEqual((totals["subagent"]["seconds"], totals["message"]["seconds"]), (20.0, 10.0))

    def test_words_per_stop_averages_the_last_message_of_each_turn(self):
        trajectory = self.trajectory(
            user(0, "# Orders"),
            agent(1, message="Reading the code first."),
            user(2, SKILL_BODY),
            agent(3, message="one two three four"),
            user(4, "Approved. Continue."),
            agent(5, bash("npm test")),
            agent(6, message="one two"),
        )
        self.assertEqual(activity.words_per_stop(trajectory), 3.0)

    def test_words_per_stop_is_none_without_a_message(self):
        self.assertIsNone(activity.words_per_stop(self.trajectory(user(0, "Fix it."), agent(1, bash("npm test")))))


if __name__ == "__main__":
    unittest.main()
