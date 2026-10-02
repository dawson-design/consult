"""Stored baselines, so a run can reuse earlier bare and Consult jobs.

The bare arm reads no skills, so a skill edit cannot change it. A baseline
records the bare and Consult job dirs of a full run, and the stub job dir when
that arm ran, together with a key: the agent, model, effort, CLI version, and
a hash of every task dir. A later run reuses the stored bare job when its key
matches for the tasks it runs, and compares its Consult arm against the stored
one. Standard library only, so the tests run in CI.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

EVAL_DIR = Path(__file__).resolve().parent.parent
BASELINES_DIR = EVAL_DIR / "runs" / "baselines"


def task_hash(task_dir: Path) -> str:
    """sha256 over every file's relative path and bytes; any change to the task changes it."""
    digest = hashlib.sha256()
    for path in sorted(p for p in task_dir.rglob("*") if p.is_file() and "__pycache__" not in p.parts):
        digest.update(path.relative_to(task_dir).as_posix().encode() + b"\0")
        digest.update(path.read_bytes() + b"\0")
    return digest.hexdigest()


def baseline_key(agent: dict, effort: str | None, tasks: list[str], harbor_args: list[str] = ()) -> dict:
    """harbor_args are the caller's own extra args; a tier's judge toggle is left out, since lift.py aligns it."""
    kwargs = agent.get("kwargs") or {}
    return {
        "agent": agent.get("name"),
        "model": agent.get("model_name"),
        "effort": effort or kwargs.get("reasoning_effort"),
        "version": kwargs.get("version"),
        "kwargs": {k: v for k, v in kwargs.items() if k != "reasoning_effort"},
        "harbor_args": list(harbor_args),
        "tasks": {t: task_hash(EVAL_DIR / "tasks" / t) for t in tasks},
    }


def mismatch(stored: dict, current: dict) -> str | None:
    """Why a stored key cannot stand in for the current one, or None when it can."""
    for field in ("agent", "model", "effort", "version", "kwargs", "harbor_args"):
        if stored.get(field) != current.get(field):
            return f"{field} differs: baseline {stored.get(field)!r}, this run {current.get(field)!r}"
    stored_tasks = stored.get("tasks") or {}
    missing = [t for t in current["tasks"] if t not in stored_tasks]
    if missing:
        return f"baseline has no run of {', '.join(missing)}"
    changed = [t for t, h in current["tasks"].items() if stored_tasks[t] != h]
    return f"task changed since the baseline: {', '.join(changed)}" if changed else None


def unrewarded_trials(job_dir: Path) -> list[str]:
    """Trials without a reward: agent or verifier failures that would score 0 in every later comparison."""
    missing = []
    for result_path in sorted(job_dir.glob("*/result.json")):
        rewards = (json.loads(result_path.read_text()).get("verifier_result") or {}).get("rewards") or {}
        if rewards.get("reward") is None:
            missing.append(result_path.parent.name)
    return missing


def load(name: str) -> dict | None:
    path = BASELINES_DIR / f"{name}.json"
    return json.loads(path.read_text()) if path.is_file() else None


def save(name: str, key: dict, bare_job: Path, consult_job: Path, stub_job: Path | None = None) -> Path:
    BASELINES_DIR.mkdir(parents=True, exist_ok=True)
    path = BASELINES_DIR / f"{name}.json"
    jobs = {"bare": str(bare_job), "consult": str(consult_job)}
    if stub_job:
        jobs["stub"] = str(stub_job)
    path.write_text(json.dumps({"key": key, **jobs}, indent=2))
    return path
