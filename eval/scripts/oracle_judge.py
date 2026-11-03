#!/usr/bin/env python3
"""Check each task's rubric against its oracle solution with the rubric judges.

  uv run --project eval eval/scripts/oracle_judge.py [--tasks a,b] [--dry-run | --yes]

Per task it builds the task image, applies solution/solve.sh to the scaffold,
checks the result passes the visible test command and the hidden check, and
then runs tests/judge_runner.py in the container on every rubric dimension
except report: the oracle writes no final message. Every must-have item must
answer yes on the oracle. One that does not is a bug in the rubric or the
oracle, to fix before any trial is judged.

The oracle has no conversation, so the check writes one: each step's
instruction as the user's turn, and steps/<step>/solution/reply.md, when
present, as the oracle's reply. Only the report judge reads replies, and the
check skips it, so a reply is passed along but not judged.

Judge calls bill the maintainer's Claude subscription through the official
`claude` CLI in the container: one call per code dimension per task, plus up
to one retry each. Without --yes it prints the planned call count and stops.
--dry-run applies and checks the oracles and calls no judge.

Output goes to runs/oracle-judge/<timestamp>/: each task's judge-items.json
and transcripts, plus summary.md and summary.json.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path

EVAL_DIR = Path(__file__).resolve().parent.parent
TASKS_DIR = EVAL_DIR / "tasks"
RUNS_DIR = EVAL_DIR / "runs" / "oracle-judge"
sys.path.insert(0, str(EVAL_DIR / "scripts"))
from rescore import DockerError, docker, image_tag
from sync_tests import step_names

# The oracle leaves no final message, so the report judge has nothing to read.
SKIPPED_DIMENSIONS = frozenset({"report"})
JUDGE_TIMEOUT_SEC = 3600
CHECK_TIMEOUT_SEC = 300


def oracle_tasks(selected: list[str] | None) -> tuple[list[str], list[str]]:
    """Code tasks with a synced rubric, and a problem for each selected task that cannot be checked."""
    names = selected or sorted(p.parents[2].name for p in TASKS_DIR.glob("*/tests/rubric/items.json"))
    tasks, problems = [], []
    for task in names:
        if not (TASKS_DIR / task / "tests" / "rubric" / "items.json").is_file():
            problems.append(f"{task}: no rubric (tests/rubric/items.json); write one and run sync_tests.py")
        elif not (TASKS_DIR / task / "solution" / "solve.sh").is_file():
            problems.append(f"{task}: no oracle (solution/solve.sh)")
        else:
            tasks.append(task)
    return tasks, problems


def code_items(items: list[dict]) -> list[dict]:
    return [item for item in items if item["dimension"] not in SKIPPED_DIMENSIONS]


def judge_calls(items: list[dict]) -> int:
    """Calls one judge run makes on these items: one per dimension, retries aside."""
    return len({item["dimension"] for item in code_items(items)})


def task_items(task: str) -> list[dict]:
    return json.loads((TASKS_DIR / task / "tests" / "rubric" / "items.json").read_text())["items"]


def gate(result: dict) -> list[dict]:
    """The must-have items the oracle did not meet: any answer but yes, including unknown and failed calls."""
    return [r for r in result["items"] if r["tier"] == "must" and r["answer"] != "yes"]


def oracle_trajectory(task: str) -> dict:
    """The conversation a multi-step oracle would have had: each step's instruction, then its reply.md."""
    steps = []
    for name in step_names(TASKS_DIR / task):
        step = TASKS_DIR / task / "steps" / name
        reply = step / "solution" / "reply.md"
        steps.append({"source": "user", "message": (step / "instruction.md").read_text()})
        steps.append({"source": "agent", "message": reply.read_text() if reply.is_file() else ""})
    return {"steps": steps}


def exec_in(container: str, script: str, timeout: int, env: list[str] = ()) -> tuple[bool, str]:
    """Run a bash script in the container's /app; (succeeded, last 3000 characters of output)."""
    argv = ["docker", "exec", "-w", "/app", *env, container, "bash", "-c", script]
    try:
        proc = subprocess.run(argv, capture_output=True, text=True, timeout=timeout, check=False)
    except subprocess.TimeoutExpired:
        return False, f"timed out after {timeout}s"
    return proc.returncode == 0, (proc.stdout + proc.stderr)[-3000:]


def check_task(task: str, out_dir: Path, judge: bool) -> dict:
    """Apply the oracle, check it, and (when judge) run the code judges; returns the task's summary row."""
    task_dir, logs = TASKS_DIR / task, (out_dir / task).resolve()
    logs.mkdir(parents=True)
    name = f"consult-oracle-{os.getpid()}-{task}"
    row: dict = {"task": task, "oracle": None, "failed_must": None, "errors": []}
    with tempfile.TemporaryDirectory() as tmp:
        items_path, trajectory_path = Path(tmp) / "items.json", Path(tmp) / "trajectory.json"
        items_path.write_text(json.dumps({"items": code_items(task_items(task))}))
        trajectory_path.write_text(json.dumps(oracle_trajectory(task)))
        meta = json.loads((task_dir / "tests" / "consult.json").read_text())
        try:
            docker("build", "-q", "-t", image_tag(task), str(task_dir / "environment"))
            docker("run", "-d", "--name", name, "-v", f"{logs}:/logs/verifier", image_tag(task), "sleep", "infinity")
            docker("cp", f"{task_dir / 'tests'}/.", f"{name}:/tests")
            docker("cp", str(items_path), f"{name}:/tests/rubric/items.json")
            docker("cp", f"{task_dir / 'solution'}/.", f"{name}:/solution")
            exec_in(name, "mkdir -p /logs/agent", CHECK_TIMEOUT_SEC)
            docker("cp", str(trajectory_path), f"{name}:/logs/agent/trajectory.json")
            checks = [
                ("solve.sh", "bash /solution/solve.sh"),
                ("visible tests", meta["visible_test_cmd"]),
                ("hidden check", 'node --input-type=module -e "$(cat /tests/hidden.mjs)"'),
            ]
            for label, script in checks:
                ok, output = exec_in(name, script, CHECK_TIMEOUT_SEC)
                if not ok:
                    row["errors"].append(f"{label} failed: {output}")
            row["oracle"] = "pass" if not row["errors"] else "fail"
            if judge and row["oracle"] == "pass":
                env = ["-e", "CLAUDE_CODE_OAUTH_TOKEN"]
                ok, output = exec_in(name, "python3 /tests/judge_runner.py", JUDGE_TIMEOUT_SEC, env)
                if not ok:
                    row["errors"].append(f"judge_runner.py failed: {output}")
                judged(row, logs / "judge-items.json")
        except DockerError as error:
            row["errors"].append(str(error))
        finally:
            subprocess.run(["docker", "rm", "-f", name], capture_output=True, check=False)
    return row


def judged(row: dict, answers_path: Path) -> None:
    """Fill the row from the runner's answers: failed calls and the must items the oracle missed."""
    if not answers_path.is_file():
        row["errors"].append("the runner wrote no judge-items.json")
        return
    result = json.loads(answers_path.read_text())
    row["errors"] += [f"{c['dimension']} judge: {c['error']}" for c in result["calls"] if c["error"]]
    row["failed_must"] = [{k: r[k] for k in ("id", "answer", "evidence", "why")} for r in gate(result)]
    row["unknown"] = result["unknown"]


def render(rows: list[dict], judged_run: bool) -> str:
    lines = [
        "# Oracle judge check",
        "",
        "| task | oracle | must items missed | errors |",
        "| --- | --- | ---: | ---: |",
    ]
    for row in rows:
        missed = "-" if row["failed_must"] is None else str(len(row["failed_must"]))
        lines.append(f"| {row['task']} | {row['oracle'] or '-'} | {missed} | {len(row['errors'])} |")
    if not judged_run:
        lines += ["", "Dry run: no judge was called."]
    for row in rows:
        for item in row["failed_must"] or []:
            lines += ["", f"- {row['task']} `{item['id']}`: {item['answer']}. {item['why']} ({item['evidence']})"]
        for error in row["errors"]:
            lines += ["", f"- {row['task']}: {error.splitlines()[0] if error else error}"]
    return "\n".join(lines) + "\n"


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--tasks", help="comma-separated task names (default: every task with a rubric)")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="apply and check the oracles; call no judge")
    mode.add_argument("--yes", action="store_true", help="run the judges after printing the call count")
    args = parser.parse_args(argv[1:])
    tasks, problems = oracle_tasks(args.tasks.split(",") if args.tasks else None)
    for problem in problems:
        print(f"skipped {problem}", file=sys.stderr)
    calls = sum(judge_calls(task_items(t)) for t in tasks)
    print(f"{len(tasks)} tasks, {calls} judge calls (up to {2 * calls} with retries)")
    if not (args.dry_run or args.yes):
        print("Nothing run. Pass --dry-run to check the oracles, or --yes to run the judges.")
        return 0
    if args.yes and not os.environ.get("CLAUDE_CODE_OAUTH_TOKEN"):
        print("CLAUDE_CODE_OAUTH_TOKEN is not set; the judges bill the subscription through it.", file=sys.stderr)
        return 2
    out_dir = RUNS_DIR / datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    rows = []
    for task in tasks:
        print(f"checking {task}", flush=True)
        rows.append(check_task(task, out_dir, judge=args.yes))
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "summary.json").write_text(json.dumps(rows, indent=2) + "\n")
    (out_dir / "summary.md").write_text(render(rows, judged_run=args.yes))
    print(render(rows, judged_run=args.yes))
    failed = any(row["errors"] or row["failed_must"] for row in rows)
    return 1 if failed or problems else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
