"""Skill-loading preflight: does the consult arm load Consult at all?

A long run is meaningless when the agent never reads a Consult skill, and that
takes minutes to check. run.py calls this before the arms: it runs only each
task's first turn in the consult arm, with verification off, and reads which
skills each trajectory loaded. Standard library only, so the tests run in CI.
"""

from __future__ import annotations

import json
import re
import shutil
import sys
from collections import Counter
from itertools import chain
from pathlib import Path

EVAL_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(EVAL_DIR / "verifier" / "shared"))
import consult_lib as cl  # noqa: E402

STEP_NAME_RE = re.compile(r'^\[\[steps\]\]\s*\n\s*name\s*=\s*"([^"]+)"', re.MULTILINE)


def first_turn_task(src: Path, dest: Path) -> None:
    """Copy a task keeping only its first turn: a multi-step task becomes its brief step."""
    shutil.rmtree(dest, ignore_errors=True)
    shutil.copytree(src, dest)
    config = (dest / "task.toml").read_text()
    steps = STEP_NAME_RE.findall(config)
    if not steps:
        return
    shutil.copyfile(src / "steps" / steps[0] / "instruction.md", dest / "instruction.md")
    single = re.sub(r"^multi_step_reward_strategy.*\n", "", config.split("[[steps]]")[0], flags=re.MULTILINE)
    (dest / "task.toml").write_text(single)
    shutil.rmtree(dest / "steps")


def trial_skills(trial_dir: Path) -> list[str]:
    """Consult skills read in any of the trial's trajectories: one per step in a multi-step trial."""
    paths = [trial_dir / "agent" / "trajectory.json", *sorted(trial_dir.glob("steps/*/agent/trajectory.json"))]
    return sorted(set(chain.from_iterable(cl.read_skill_names(cl.load_trajectory(p)) for p in paths)))


def trial_task(trial_dir: Path) -> str:
    result = trial_dir / "result.json"
    name = json.loads(result.read_text()).get("task_name") if result.is_file() else None
    return (name or trial_dir.name.split("__")[0]).split("/")[-1]


def loading_rows(job_dir: Path) -> list[dict]:
    """Per task: trials run, trials that read any Consult skill, and how often each skill was read."""
    by_task: dict[str, list[list[str]]] = {}
    for trial_dir in sorted(p.parent for p in job_dir.glob("*/result.json")):
        by_task.setdefault(trial_task(trial_dir), []).append(trial_skills(trial_dir))
    return [
        {"task": task, "trials": len(runs), "loaded": sum(1 for skills in runs if skills),
         "skills": Counter(chain.from_iterable(runs))}
        for task, runs in sorted(by_task.items())
    ]


def loading_rate(rows: list[dict]) -> float:
    trials = sum(r["trials"] for r in rows)
    return sum(r["loaded"] for r in rows) / trials if trials else 0.0


def render(rows: list[dict]) -> str:
    lines = ["| task | loaded Consult | skills read (trials) |", "| --- | ---: | --- |"]
    for row in rows:
        skills = ", ".join(f"{name} ({n})" for name, n in row["skills"].most_common()) or "none"
        lines.append(f"| {row['task']} | {row['loaded']}/{row['trials']} | {skills} |")
    lines.append(f"\nLoading rate: {loading_rate(rows):.0%}")
    return "\n".join(lines)
