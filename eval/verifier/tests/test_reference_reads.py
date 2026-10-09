"""Which skill reference files trials opened: the read-frequency input to the reference audit.

  python3 -m unittest discover eval/verifier/tests

Fixtures follow real Harbor trajectories: Claude Code opens a file with the
`Read` tool, Codex with `exec_command` (sed or cat).
"""

from __future__ import annotations

import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

EVAL_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(EVAL_DIR / "scripts"))

import reference_reads  # noqa: E402

CLAUDE_SKILLS = "/logs/agent/sessions/skills"
CODEX_SKILLS = "/root/.agents/skills"


def call_step(name: str, arguments: dict, result: str = "", error: bool = False) -> dict:
    extra = {"tool_result_is_error": True} if error else {}
    return {
        "source": "agent",
        "message": "",
        "tool_calls": [{"tool_call_id": "c1", "function_name": name, "arguments": arguments}],
        "observation": {"results": [{"source_call_id": "c1", "content": result, "extra": extra}]},
    }


def claude_read(path: str, error: bool = False) -> dict:
    return call_step("Read", {"file_path": path}, "File does not exist." if error else "contents", error)


def codex_exec(cmd: str, result: str = "contents") -> dict:
    return call_step("exec_command", {"cmd": cmd}, result)


def write_trajectory(path: Path, *steps: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"steps": [{"step_id": i, **s} for i, s in enumerate(steps, start=1)]}))


class ReferenceReadsTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def trial(self, job: str, name: str, *steps: dict) -> Path:
        trial = self.root / job / name
        write_trajectory(trial / "agent" / "trajectory.json", *steps)
        (trial / "result.json").write_text(json.dumps({"task_name": "consult/api-error-contract"}))
        return trial

    def test_a_reference_read_twice_counts_once_and_a_failed_read_not_at_all(self):
        trial = self.trial("consult", "t__0",
                           claude_read(f"{CLAUDE_SKILLS}/api/references/rest-error-status-codes.md"),
                           claude_read(f"{CLAUDE_SKILLS}/api/references/rest-error-status-codes.md"),
                           claude_read(f"{CLAUDE_SKILLS}/api/references/pagination.md", error=True))
        self.assertEqual(reference_reads.trial_references(trial), {"api/references/rest-error-status-codes.md"})

    def test_a_codex_shell_read_counts(self):
        trial = self.trial("consult", "t__0", codex_exec(f"sed -n 1,200p {CODEX_SKILLS}/security/references/secrets.md"))
        self.assertEqual(reference_reads.trial_references(trial), {"security/references/secrets.md"})

    def test_a_listing_that_shows_reference_paths_is_not_a_read(self):
        listing = f"{CODEX_SKILLS}/security/references/secrets.md\n{CODEX_SKILLS}/security/references/infra.md"
        trial = self.trial("consult", "t__0", codex_exec(f"ls {CODEX_SKILLS}/security/references", listing))
        self.assertEqual(reference_reads.trial_references(trial), set())

    def test_every_step_trajectory_of_a_multi_step_trial_counts(self):
        trial = self.trial("consult", "t__0")
        write_trajectory(trial / "steps" / "brief" / "agent" / "trajectory.json",
                         claude_read(f"{CLAUDE_SKILLS}/domain-modeling/references/money.md"))
        write_trajectory(trial / "steps" / "build" / "agent" / "trajectory.json",
                         claude_read(f"{CLAUDE_SKILLS}/proof/references/test-theater.md"))
        self.assertEqual(reference_reads.trial_references(trial),
                         {"domain-modeling/references/money.md", "proof/references/test-theater.md"})

    def test_the_report_shows_each_reference_per_job_including_ones_nobody_opened(self):
        self.trial("bare", "t__0")
        self.trial("consult", "t__0", claude_read(f"{CLAUDE_SKILLS}/workflow/references/long-runs.md"))
        self.trial("consult", "t__1")
        with redirect_stdout(io.StringIO()) as out:
            reference_reads.main(["reference_reads.py", str(self.root / "bare"), str(self.root / "consult")])
        report = out.getvalue()
        self.assertIn("| workflow/references/long-runs.md | 0/1 | 1/2 |", report)
        self.assertIn("| workflow/references/simple-not-easy.md | 0/1 | 0/2 |", report)


if __name__ == "__main__":
    unittest.main()
