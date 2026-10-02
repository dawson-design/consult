"""Which Consult skills a trajectory loaded: the skill_triggering readout, preflight, and lift's skills scorecard.

  python3 -m unittest discover eval/verifier/tests

Fixtures follow real Harbor trajectories: Claude Code invokes a skill with the
`Skill` tool and injects the body as a user message, Codex reads SKILL.md with
`exec_command` (sed or cat).
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

EVAL_DIR = Path(__file__).resolve().parents[2]
SKILLS_DIR = EVAL_DIR.parent / "agents" / ".agents" / "skills"
sys.path.insert(0, str(EVAL_DIR / "verifier" / "shared"))

import consult_lib as cl  # noqa: E402


INSTALLED_SKILLS = "/logs/agent/sessions/skills"


def call_step(name: str, arguments: dict, result: str = "", error: bool = False) -> dict:
    extra = {"tool_result_is_error": True} if error else {}
    return {
        "source": "agent",
        "message": "",
        "tool_calls": [{"tool_call_id": "c1", "function_name": name, "arguments": arguments}],
        "observation": {"results": [{"source_call_id": "c1", "content": result, "extra": extra}]},
    }


def skill_call(name: str, injected: str) -> list[dict]:
    """A Skill call Claude Code accepted, then the prompt it injects as a user message."""
    result = f'Launching skill: {name}\n\n[metadata] {{"success": true, "commandName": "{name}"}}'
    return [call_step("Skill", {"skill": name}, result), {"source": "user", "message": injected}]


def skill_file_load(name: str, skill_dir: str) -> list[dict]:
    return skill_call(name, f"Base directory for this skill: {skill_dir}\n\n# {name}\n\nBody.")


def skills_read(*steps: dict) -> list[str]:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "trajectory.json"
        numbered = [{"step_id": i, **s} for i, s in enumerate(steps, start=1)]
        path.write_text(json.dumps({"steps": numbered}))
        return cl.read_skill_names(cl.load_trajectory(path))


class SkillDetectionTests(unittest.TestCase):
    def test_the_catalog_matches_the_canonical_skill_dirs(self):
        on_disk = {p.parent.name for p in SKILLS_DIR.glob("*/SKILL.md")}
        self.assertEqual(set(cl.CONSULT_SKILLS), on_disk)

    def test_a_skill_path_seen_only_in_a_tool_result_is_not_counted(self):
        listing = "/root/.claude/skills/workflow/SKILL.md\n/root/.claude/skills/debugging/SKILL.md"
        step = call_step("Bash", {"command": "find / -name SKILL.md"}, listing)
        self.assertEqual(skills_read(step), [])

    def test_an_installed_skill_that_claude_code_loaded_is_counted(self):
        steps = [*skill_file_load("workflow", f"{INSTALLED_SKILLS}/workflow"), *skill_file_load("debugging", f"{INSTALLED_SKILLS}/debugging")]
        self.assertEqual(skills_read(*steps), ["debugging", "workflow"])

    def test_a_consult_plugin_skill_load_is_counted(self):
        plugin_dir = "/root/.claude/plugins/cache/consult/consult/15.2.0/skills/debugging"
        self.assertEqual(skills_read(*skill_file_load("consult:debugging", plugin_dir)), ["debugging"])

    def test_a_skill_outside_the_catalog_is_not_counted(self):
        plugin_dir = "/root/.claude/plugins/cache/frontend-design/frontend-design/1.0.0/skills/frontend-design"
        self.assertEqual(skills_read(*skill_file_load("frontend-design:frontend-design", plugin_dir)), [])

    def test_a_bundled_skill_sharing_a_consult_name_is_not_counted(self):
        extracted = "/logs/agent/sessions/bundled-skills/2.1.282/0a1b2c3d/commit"
        steps = [*skill_call("code-review", "Review the current diff for bugs."), *skill_file_load("commit", extracted)]
        self.assertEqual(skills_read(*steps), [])

    def test_a_skill_call_claude_code_rejected_is_not_counted(self):
        step = call_step("Skill", {"skill": "consult:workflow"}, "Unknown skill: consult:workflow", error=True)
        self.assertEqual(skills_read(step), [])

    def test_a_codex_shell_read_of_skill_md_is_counted(self):
        cmd = "sed -n '1,220p' /root/.agents/skills/code-review/SKILL.md && cat /root/.agents/skills/workflow/SKILL.md"
        step = call_step("exec_command", {"cmd": cmd, "yield_time_ms": 10000}, "Process exited with code 0\nOutput:\n")
        self.assertEqual(skills_read(step), ["code-review", "workflow"])


if __name__ == "__main__":
    unittest.main()
