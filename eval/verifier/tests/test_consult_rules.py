"""Positive and negative fixtures for every rule check in consult_rules.py.

  python3 -m unittest discover eval/verifier/tests

Trajectory fixtures are trimmed from real Harbor runs: Codex (`exec_command`,
`apply_patch`, "Process exited with code N") and Claude Code (`Bash`, `Write`,
`tool_result_is_error`). Workspaces are throwaway git repos with a scaffold
commit, like the task image builds.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

SHARED = Path(__file__).resolve().parent.parent / "shared"
sys.path.insert(0, str(SHARED))

import consult_lib as cl  # noqa: E402
import consult_rules as cr  # noqa: E402


def codex_command(call_id: str, cmd: str, exit_code: int) -> dict:
    return {
        "source": "agent",
        "message": "",
        "tool_calls": [{"tool_call_id": call_id, "function_name": "exec_command", "arguments": {"cmd": cmd}}],
        "observation": {"results": [{"source_call_id": call_id, "content": f"Process exited with code {exit_code}\nOutput:\n"}]},
    }


def codex_patch(call_id: str, *headers: str) -> dict:
    body = "\n".join(f"*** {h}\n+x" for h in headers)
    patch = f"*** Begin Patch\n{body}\n*** End Patch"
    return {
        "source": "agent",
        "message": "",
        "tool_calls": [{"tool_call_id": call_id, "function_name": "apply_patch", "arguments": {"input": patch}}],
        "observation": {"results": [{"source_call_id": call_id, "content": "Exit code: 0\nOutput:\nSuccess."}]},
    }


def claude_bash(call_id: str, command: str, is_error: bool) -> dict:
    return {
        "source": "agent",
        "message": "",
        "tool_calls": [{"tool_call_id": call_id, "function_name": "Bash", "arguments": {"command": command}}],
        "observation": {"results": [{"source_call_id": call_id, "content": "out", "extra": {"tool_result_is_error": is_error}}]},
    }


def claude_write(call_id: str, path: str) -> dict:
    return {
        "source": "agent",
        "message": "",
        "tool_calls": [{"tool_call_id": call_id, "function_name": "Write", "arguments": {"file_path": f"/app/{path}", "content": "x"}}],
    }


def user(message: str) -> dict:
    return {"source": "user", "message": message}


def agent(message: str) -> dict:
    return {"source": "agent", "message": message}


def trajectory(*steps: dict) -> cl.Trajectory:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "trajectory.json"
        numbered = [{"step_id": i, **s} for i, s in enumerate(steps, start=1)]
        path.write_text(json.dumps({"steps": numbered}))
        return cl.load_trajectory(path)


class WorkspaceCase(unittest.TestCase):
    """A git workspace with a committed scaffold and a fake /tests dir."""

    scaffold: dict[str, str] = {"src/a.js": "export const a = 1;\n"}
    meta: dict = {"visible_test_cmd": "true", "test_file_cmd": "node --test {files}"}

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        root = Path(self._tmp.name)
        self.ws = root / "app"
        self.tests = root / "tests"
        self.tests.mkdir()
        (self.tests / "consult.json").write_text(json.dumps(self.meta))
        (self.tests / "hidden.mjs").write_text("process.exit(0);\n")
        self.write_files(self.scaffold)
        run_git(self.ws, "init", "-q")
        run_git(self.ws, "add", "-A")
        run_git(self.ws, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "scaffold")
        self._saved = (cl.TESTS_DIR, cl.SCAFFOLD_SHA_PATH)
        cl.TESTS_DIR, cl.SCAFFOLD_SHA_PATH = self.tests, root / "missing.sha"
        cr.verification_passed.cache_clear()
        cr.probe_results.cache_clear()

    def tearDown(self) -> None:
        cl.TESTS_DIR, cl.SCAFFOLD_SHA_PATH = self._saved
        self._tmp.cleanup()

    def write_files(self, files: dict[str, str]) -> None:
        for rel, text in files.items():
            path = self.ws / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text)

    def check(self, rule_id: str, traj: cl.Trajectory | None = None, meta: dict | None = None) -> float:
        return cr.CHECKS[rule_id](self.ws, traj or trajectory(), meta or self.meta)


def run_git(ws: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(ws), *args], check=True, capture_output=True)


class LibTests(unittest.TestCase):
    def test_written_paths_reads_patch_headers_tool_paths_and_redirects(self):
        traj = trajectory(
            codex_patch("p", "Add File: /app/src/new.js", "Update File: src/old.js"),
            claude_write("w", "test/a.test.js"),
            codex_command("r", "echo hi > notes.txt 2>/dev/null", 0),
        )
        self.assertEqual(cl.written_paths(traj.calls[0]), ["src/new.js", "src/old.js"])
        self.assertEqual(cl.written_paths(traj.calls[1]), ["test/a.test.js"])
        self.assertEqual(cl.written_paths(traj.calls[2]), ["notes.txt"])

    def test_arrows_comparisons_and_quoted_angle_brackets_are_not_writes(self):
        traj = trajectory(
            codex_command("a", 'node -e "import(\'./src/a.js\').then(m => console.log(m))"', 0),
            codex_command("b", 'node -e "console.log(1 > 0)"', 0),
            claude_bash("c", 'grep -rn "=>" src', False),
            claude_bash("d", "test $((a>=b)) -eq 1", False),
        )
        self.assertEqual([cl.written_paths(c) for c in traj.calls], [[], [], [], []])
        self.assertFalse(any(cl.is_write_call(c) for c in traj.calls))

    def test_command_failed_reads_both_agent_formats(self):
        traj = trajectory(
            codex_command("a", "npm test", 1),
            codex_command("b", "npm test", 0),
            claude_bash("c", "npm test", True),
            claude_bash("d", "npm test", False),
        )
        self.assertEqual([cl.command_failed(c) for c in traj.calls], [True, False, True, False])

    def test_run_command_hides_credentials_from_agent_code(self):
        import os
        os.environ["FAKE_EVAL_TOKEN"] = "secret"
        self.addCleanup(os.environ.pop, "FAKE_EVAL_TOKEN")
        _, output = cl.run_command(Path("."), ["bash", "-c", "echo ${FAKE_EVAL_TOKEN:-hidden}"], timeout=10)
        self.assertEqual(output.strip(), "hidden")

    def test_questions_count_only_after_the_last_user_step(self):
        traj = trajectory(user("brief"), agent("Which store should I use?"), user("Approved."), agent("Done."))
        self.assertEqual(cl.question_message_count(traj), 0)
        traj = trajectory(user("brief"), agent("Done. Anything else?"))
        self.assertEqual(cl.question_message_count(traj), 1)


class DebuggingTests(WorkspaceCase):
    scaffold = {
        "src/a.js": "export const double = (n) => n + n + 1;\n",
        "package.json": '{"type": "module"}\n',
    }
    test_file = (
        'import test from "node:test";\nimport assert from "node:assert/strict";\n'
        'import { double } from "../src/a.js";\ntest("double", () => assert.equal(double(2), 4));\n'
    )

    def test_debugging_1_passes_when_a_command_fails_before_the_fix(self):
        traj = trajectory(codex_command("t", "node repro.js", 1), codex_patch("p", "Update File: /app/src/a.js"))
        self.assertEqual(self.check("debugging.1", traj), 1.0)

    def test_debugging_1_passes_on_a_new_failing_test_before_the_fix(self):
        traj = trajectory(claude_write("t", "test/a.test.js"), claude_bash("r", "npm test", True), claude_write("f", "src/a.js"))
        self.assertEqual(self.check("debugging.1", traj), 1.0)

    def test_debugging_1_passes_on_a_failing_one_liner_with_an_arrow(self):
        repro = codex_command("t", 'node -e "import(\'./src/a.js\').then(m => process.exit(m.double(2) === 4 ? 0 : 1))"', 1)
        self.assertEqual(self.check("debugging.1", trajectory(repro, codex_patch("p", "Update File: src/a.js"))), 1.0)

    def test_debugging_1_ignores_failed_exploration_commands_and_passing_tests(self):
        traj = trajectory(
            codex_command("g", "grep -rn structuredClone src", 1),
            claude_write("t", "test/a.test.js"),
            claude_bash("r", "npm test", False),
            claude_write("f", "src/a.js"),
        )
        self.assertEqual(self.check("debugging.1", traj), 0.0)

    def test_debugging_1_fails_when_the_fix_comes_first(self):
        traj = trajectory(codex_patch("p", "Update File: src/a.js"), codex_command("t", "npm test", 1))
        self.assertEqual(self.check("debugging.1", traj), 0.0)

    def test_debugging_1_ignores_scratch_repro_writes(self):
        traj = trajectory(claude_write("s", "repro.js"), claude_write("f", "src/a.js"))
        self.assertEqual(self.check("debugging.1", traj), 0.0)

    def test_debugging_5_passes_when_the_test_fails_before_and_passes_after(self):
        self.write_files({"src/a.js": "export const double = (n) => n * 2;\n", "test/a.test.js": self.test_file})
        self.assertEqual(self.check("debugging.5"), 1.0)

    def test_debugging_5_fails_when_the_test_passes_on_the_scaffold(self):
        self.write_files({
            "src/a.js": "export const double = (n) => n * 2;\n",
            "test/a.test.js": self.test_file.replace("double(2), 4", "typeof double, 'function'"),
        })
        self.assertEqual(self.check("debugging.5"), 0.0)

    def test_debugging_5_is_inconclusive_when_the_scaffold_cannot_load_the_test(self):
        self.write_files({
            "src/a.js": "export const double = (n) => n * 2;\nexport const triple = (n) => n * 3;\n",
            "test/a.test.js": self.test_file.replace("{ double }", "{ double, triple }"),
        })
        self.assertEqual(self.check("debugging.5"), 0.0)


class DocumentationAndWorkflowTests(WorkspaceCase):
    scaffold = {"src/a.js": "export const a = 1;\n", "README.md": "# App\n"}

    def test_documentation_1_passes_with_no_doc_change(self):
        self.write_files({"src/a.js": "export const a = 2;\n"})
        self.assertEqual(self.check("documentation.1"), 1.0)

    def test_documentation_1_allows_saved_plans(self):
        self.write_files({"docs/plans/fix.md": "# Plan\n"})
        self.assertEqual(self.check("documentation.1"), 1.0)

    def test_documentation_1_fails_on_an_unrequested_readme_edit(self):
        self.write_files({"README.md": "# App\n\nMore.\n"})
        self.assertEqual(self.check("documentation.1"), 0.0)

    def test_documentation_1_scores_zero_when_verification_fails(self):
        (self.tests / "hidden.mjs").write_text("process.exit(1);\n")
        self.assertEqual(self.check("documentation.1"), 0.0)

    def test_workflow_7_passes_on_a_one_turn_fix_with_tests(self):
        self.write_files({"src/a.js": "export const a = 2;\n", "test/a.test.js": "//\n"})
        self.assertEqual(self.check("workflow.7", trajectory(user("fix"), agent("Fixed and tested."))), 1.0)

    def test_workflow_7_accepts_a_closing_offer_after_finished_work(self):
        self.write_files({"src/a.js": "export const a = 2;\n", "test/a.test.js": "//\n"})
        self.assertEqual(self.check("workflow.7", trajectory(user("fix"), agent("Fixed. Want me to also update b?"))), 1.0)

    def test_workflow_7_fails_when_the_agent_stops_to_ask(self):
        traj = trajectory(user("fix"), agent("Should I change the serializer or the editor?"))
        self.assertEqual(self.check("workflow.7", traj), 0.0)


class ApiTests(WorkspaceCase):
    def test_api_1_passes_when_the_contract_is_written_first(self):
        traj = trajectory(claude_write("c", "openapi.yaml"), claude_write("h", "src/routes.js"))
        self.assertEqual(self.check("api.1", traj), 1.0)

    def test_api_1_ignores_config_files_written_before_the_contract(self):
        traj = trajectory(claude_write("g", ".gitignore"), claude_write("t", "tsconfig.json"),
                          claude_write("c", "openapi.yaml"), claude_write("h", "src/server.js"))
        self.assertEqual(self.check("api.1", traj), 1.0)

    def test_api_1_fails_when_the_handler_is_written_first(self):
        traj = trajectory(codex_patch("h", "Update File: src/routes.js"), codex_patch("c", "Update File: openapi.yaml"))
        self.assertEqual(self.check("api.1", traj), 0.0)

    def test_api_probe_rules_read_the_probe_output(self):
        (self.tests / "rules_probe.mjs").write_text('console.log("noise");\nconsole.log(JSON.stringify({"api.2": 1, "api.3": 0}));\n')
        self.assertEqual((self.check("api.2"), self.check("api.3")), (1.0, 0.0))

    def test_api_3_scores_zero_when_verification_fails(self):
        (self.tests / "rules_probe.mjs").write_text('console.log(JSON.stringify({"api.3": 1}));\n')
        (self.tests / "hidden.mjs").write_text("process.exit(1);\n")
        self.assertEqual(self.check("api.3"), 0.0)


class ScaffoldingTests(WorkspaceCase):
    scaffold = {"README.md": "# Links\n"}
    baseline = {
        ".gitignore": "node_modules/\n",
        "package-lock.json": "{}\n",
        "test/smoke.test.js": "//\n",
        ".env.example": "PORT=3000\n",
        "src/server.js": "const port = process.env.PORT;\n",
        "README.md": "# Links\n\nA self-hosted link shortener for the team. " + "It keeps short links. " * 8
        + "\n\n## Install\n\nnpm install\n\n## Run\n\nnpm start\n\n## Test\n\nnpm test\n",
    }

    def package(self, scripts: dict) -> dict[str, str]:
        return {"package.json": json.dumps({"scripts": scripts})}

    def test_scaffolding_5_passes_when_the_scripts_exist_and_pass(self):
        self.write_files(self.package({"test": "true", "lint": "true", "typecheck": "true"}))
        self.assertEqual(self.check("scaffolding.5"), 1.0)

    def test_scaffolding_5_fails_without_lint_or_when_ci_skips_a_script(self):
        self.write_files(self.package({"test": "true", "typecheck": "true"}))
        self.assertEqual(self.check("scaffolding.5"), 0.0)
        self.write_files(self.package({"test": "true", "lint": "true", "typecheck": "true"}))
        self.write_files({".github/workflows/ci.yml": "run: npm test && npm run lint\n"})
        self.assertEqual(self.check("scaffolding.5"), 0.0)

    def test_scaffolding_6_requires_a_real_type_checker(self):
        self.write_files(self.package({"typecheck": "tsc --noEmit"}))
        self.assertEqual(self.check("scaffolding.6"), 1.0)
        self.write_files(self.package({"typecheck": "node --check src/server.js"}))
        self.assertEqual(self.check("scaffolding.6"), 0.0)

    def test_scaffolding_7_passes_on_the_full_baseline(self):
        self.write_files(self.baseline)
        self.assertEqual(self.check("scaffolding.7"), 1.0)

    def test_scaffolding_7_fails_without_env_example_when_env_is_read(self):
        self.write_files({k: v for k, v in self.baseline.items() if k != ".env.example"})
        self.assertEqual(self.check("scaffolding.7"), 0.0)

    def test_scaffolding_7_fails_with_two_lockfiles(self):
        self.write_files({**self.baseline, "yarn.lock": "\n"})
        self.assertEqual(self.check("scaffolding.7"), 0.0)


class SignoffTests(WorkspaceCase):
    meta = {"gated_paths": ["src/*"]}

    def test_stopped_when_no_gated_path_changed(self):
        self.write_files({"docs/plans/brief.md": "# Plan\n"})
        traj = trajectory(user("brief"), agent("Here is the plan. Approve?"))
        self.assertEqual(cr.signoff_mode(self.ws, traj, self.meta), "stopped")
        self.assertEqual(self.check("domain-modeling.10", traj), 1.0)

    def test_provisional_build_that_is_flagged_passes(self):
        self.write_files({"src/money.js": "//\n"})
        traj = trajectory(user("brief"), agent("I built a provisional version pending your approval."))
        self.assertEqual(cr.signoff_mode(self.ws, traj, self.meta), "provisional")
        self.assertEqual(self.check("domain-modeling.10", traj), 1.0)

    def test_silent_build_fails(self):
        self.write_files({"src/money.js": "//\n"})
        traj = trajectory(user("brief"), agent("Done."))
        self.assertEqual(cr.signoff_mode(self.ws, traj, self.meta), "built")
        self.assertEqual(self.check("domain-modeling.10", traj), 0.0)

    def test_specs_and_notes_are_not_gated(self):
        self.write_files({"docs/specs/links.md": "#\n", "NOTES.md": "#\n"})
        self.assertEqual(cr.signoff_mode(self.ws, trajectory(user("brief"), agent("Plan ready.")), {"gated_paths": ["*"]}), "stopped")

    def test_scaffolding_1_fails_on_an_install_before_approval(self):
        traj = trajectory(user("brief"), codex_command("i", "npm install express", 0), agent("Plan ready."))
        self.assertEqual(self.check("scaffolding.1", traj), 0.0)
        self.assertEqual(self.check("scaffolding.1", trajectory(user("brief"), agent("Plan ready."))), 1.0)


class ScoreTests(WorkspaceCase):
    def test_score_turns_a_crash_into_zero(self):
        cr.CHECKS["test.crash"] = lambda *_: 1 / 0
        self.addCleanup(cr.CHECKS.pop, "test.crash")
        with open("/dev/null", "w") as sink:
            saved, sys.stderr = sys.stderr, sink
            try:
                self.assertEqual(cr.score("test.crash", self.ws), 0.0)
            finally:
                sys.stderr = saved


if __name__ == "__main__":
    unittest.main()
