"""Pick the fast-tier tasks for the skills changed since a git ref.

A task matches a skill when its tests/consult.json lists the skill in
intended_skills or scores one of its rules. Tasks where the skill is one of
fewer intended skills come first, since the skill carries more of their
outcome. Standard library only, so the tests run in CI.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

EVAL_DIR = Path(__file__).resolve().parent.parent
REPO_DIR = EVAL_DIR.parent
SKILLS_PATH = "agents/.agents/skills"


def changed_skills(ref: str) -> set[str]:
    """Skill names with tracked changes against ref, or new untracked files, under the canonical skills dir."""
    diff = git("diff", "--name-only", "--no-renames", ref, "--", SKILLS_PATH)
    untracked = git("ls-files", "--others", "--exclude-standard", "--", SKILLS_PATH)
    return {skill_name(p) for p in (diff + untracked).split() if skill_name(p)}


def git(*args: str) -> str:
    return subprocess.run(["git", "-C", str(REPO_DIR), *args], capture_output=True, text=True, check=True).stdout


def skill_name(path: str) -> str | None:
    parts = path.split("/")
    return parts[3] if len(parts) > 4 and path.startswith(SKILLS_PATH + "/") else None


def task_skills(task: str) -> tuple[set[str], set[str]]:
    """(intended skills, skills whose rules the task scores)."""
    meta = json.loads((EVAL_DIR / "tasks" / task / "tests" / "consult.json").read_text())
    rules = {r.split(".")[0] for r in meta.get("rules") or []}
    return set(meta.get("intended_skills") or []), rules


def select_tasks(skills: set[str], candidates: list[str], limit: int) -> list[str]:
    """Up to limit candidates that exercise any of skills, most specific first."""
    matches = []
    for task in candidates:
        intended, ruled = task_skills(task)
        if skills & (intended | ruled):
            matches.append((len(intended), task))
    return [task for _, task in sorted(matches)[:limit]]
