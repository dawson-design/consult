"""The skill-loading preflight: first-turn task copies and the loading readout.

  python3 -m unittest discover eval/verifier/tests
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from itertools import chain
from pathlib import Path

EVAL_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(EVAL_DIR / "scripts"))

import preflight  # noqa: E402


def skill_load(skill: str) -> list[dict]:
    """Claude Code's Skill call, then the body it injects as a user message."""
    call = {"tool_call_id": skill, "function_name": "Skill", "arguments": {"skill": skill}}
    body = f"Base directory for this skill: /logs/agent/sessions/skills/{skill}\n\n# {skill}"
    return [{"source": "agent", "message": "", "tool_calls": [call]}, {"source": "user", "message": body}]


def write_trajectory(agent_dir: Path, skills: list[str]) -> None:
    agent_dir.mkdir(parents=True)
    steps = [{"source": "user", "message": "task"}, *chain.from_iterable(skill_load(s) for s in skills)]
    numbered = [{"step_id": i, **s} for i, s in enumerate(steps, start=1)]
    (agent_dir / "trajectory.json").write_text(json.dumps({"steps": numbered}))


def new_trial(job: Path, name: str) -> Path:
    trial = job / name
    trial.mkdir(parents=True)
    (trial / "result.json").write_text(json.dumps({"task_name": f"consult/{name.split('__')[0]}"}))
    return trial


def write_trial(job: Path, name: str, skills: list[str]) -> None:
    write_trajectory(new_trial(job, name) / "agent", skills)


def write_multi_step_trial(job: Path, name: str, step_skills: dict[str, list[str]]) -> None:
    """Harbor keeps a multi-step trial's trajectories under steps/<step>/agent/, none at the root."""
    trial = new_trial(job, name)
    for step, skills in step_skills.items():
        write_trajectory(trial / "steps" / step / "agent", skills)


class FirstTurnTaskTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.out = Path(self._tmp.name)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_a_multi_step_task_becomes_its_brief_step(self):
        src = EVAL_DIR / "tasks" / "money-field-change"
        preflight.first_turn_task(src, self.out / "t")
        config = (self.out / "t" / "task.toml").read_text()
        self.assertNotIn("[[steps]]", config)
        self.assertNotIn("multi_step_reward_strategy", config)
        self.assertFalse((self.out / "t" / "steps").exists())
        self.assertEqual((self.out / "t" / "instruction.md").read_text(), (src / "steps" / "brief" / "instruction.md").read_text())

    def test_a_single_step_task_is_copied_unchanged(self):
        src = EVAL_DIR / "tasks" / "bug-from-symptom"
        preflight.first_turn_task(src, self.out / "t")
        self.assertEqual((self.out / "t" / "task.toml").read_text(), (src / "task.toml").read_text())
        self.assertEqual((self.out / "t" / "instruction.md").read_text(), (src / "instruction.md").read_text())


class LoadingTests(unittest.TestCase):
    def test_rows_and_rate_count_trials_that_read_any_skill(self):
        with tempfile.TemporaryDirectory() as tmp:
            job = Path(tmp)
            write_trial(job, "bug-from-symptom__a", ["workflow", "debugging"])
            write_trial(job, "bug-from-symptom__b", [])
            write_trial(job, "service-from-brief__c", ["workflow"])
            rows = preflight.loading_rows(job)
        self.assertEqual([(r["task"], r["loaded"], r["trials"]) for r in rows],
                         [("bug-from-symptom", 1, 2), ("service-from-brief", 1, 1)])
        self.assertAlmostEqual(preflight.loading_rate(rows), 2 / 3)
        self.assertIn("| bug-from-symptom | 1/2 | debugging (1), workflow (1) |", preflight.render(rows))

    def test_a_multi_step_trial_counts_skills_read_in_every_step(self):
        with tempfile.TemporaryDirectory() as tmp:
            job = Path(tmp)
            write_multi_step_trial(job, "money-field-change__a", {"brief": ["workflow"], "approve": ["workflow", "proof"]})
            rows = preflight.loading_rows(job)
        self.assertEqual([(r["task"], r["loaded"], r["trials"]) for r in rows], [("money-field-change", 1, 1)])
        self.assertEqual(dict(rows[0]["skills"]), {"proof": 1, "workflow": 1})


if __name__ == "__main__":
    unittest.main()
