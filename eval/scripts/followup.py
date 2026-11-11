#!/usr/bin/env python3
"""The follow-up change test: is the code one arm leaves behind cheaper to change?

  uv run --project eval eval/scripts/followup.py build runs/<bare-job> runs/<consult-job>
                        [--agent claude-code] [--attempts 1]
  uv run --project eval eval/scripts/followup.py report runs/<followup-job>

build reads two finished houseStyle jobs and writes one single-step Harbor task
per staged-commissions trial whose verification passed, under
runs/followup/<stamp>/. A task starts from that trial's final tree, rebuilt as
rescore.py rebuilds it (the task image's scaffold with the final step's
judge-bundle.md applied, so it needs Docker), and asks for the held-out sixth
change in followup/staged-commissions/instruction.md. Its verifier scores the
visible tests and the hidden check (verifier/hidden/staged-commissions-followup.mjs:
stages 1 to 5 unchanged, plus stage 6), and nothing Consult defined. build also
writes job.json, which runs every task with the agent's bare arm (no skills, no
hook), and prints the harbor command.

report reads the job that ran those tasks and prints, per source arm (trees
built by bare, trees built by consult), the pass rate, output tokens, agent
seconds, files touched, and lines changed, with the change and a 90% bootstrap
interval from lift.py. Trials are pooled per arm, each counting once; a trial
without a reward counts as a fail. Files and lines come from the follow-up
trial's judge-bundle.md, so they count only the sixth change.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import shutil
import sys
import tempfile
from collections.abc import Iterable
from pathlib import Path

EVAL_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(EVAL_DIR / "scripts"))
import lift
import rescore
import run
from bundle import RebuildError, parse_bundle

TASK = "staged-commissions"
FOLLOWUP_DIR = EVAL_DIR / "followup" / TASK
SHARED_DIR = EVAL_DIR / "verifier" / "shared"
HIDDEN_DIR = EVAL_DIR / "verifier" / "hidden"
OUT_DIR = run.RUNS_DIR / "followup"
NAME_PREFIX = "consult/followup-"
ARMS = ("bare", "consult")
TASK_TOML = """schema_version = "1.4"

[task]
name = "{name}"
description = "A held-out sixth change to a finished staged-commissions tree, made in a fresh session."

[metadata]
kind = "code"
source_arm = "{arm}"
source_trial = "{source}"

[agent]
timeout_sec = 2700.0

[verifier]
timeout_sec = 900.0
"""
METRICS = {
    "passed": ("pass rate", ".0%"),
    "output_tokens": ("output tokens", ",.0f"),
    "agent_seconds": ("agent seconds", ",.0f"),
    "files_touched": ("files touched", ",.1f"),
    "lines_changed": ("lines changed", ",.0f"),
}


# ------------------------------------------------------------------- build


def passing_trials(job: Path) -> list[rescore.Trial]:
    """The job's staged-commissions trials whose final verification passed."""
    trials = rescore.load_job(job, {TASK})
    return [t for t in trials if float(t.old_rewards.get("verification") or 0.0) == 1.0]


def task_slug(arm: str, trial: rescore.Trial) -> str:
    return re.sub(r"[^a-z0-9]+", "-", f"{arm}-{trial.name}".lower()).strip("-")


def source_arm(task_name: str) -> str | None:
    """The arm that built a follow-up task's starting tree, from the name build gave it."""
    if not task_name.startswith(NAME_PREFIX):
        return None
    slug = task_name.removeprefix(NAME_PREFIX)
    return next((arm for arm in ARMS if slug.startswith(f"{arm}-")), None)


def write_task(dest: Path, workspace: Path, arm: str, trial: rescore.Trial) -> None:
    """A single-step Harbor task whose starting repository is the rebuilt workspace."""
    shutil.copytree(
        workspace, dest / "environment" / "workspace", ignore=shutil.ignore_patterns(".git", "node_modules")
    )
    shutil.copy2(rescore.TASKS_DIR / TASK / "environment" / "Dockerfile", dest / "environment" / "Dockerfile")
    shutil.copy2(FOLLOWUP_DIR / "instruction.md", dest / "instruction.md")
    source = f"{trial.job.name}/{trial.name}"
    (dest / "task.toml").write_text(TASK_TOML.format(name=NAME_PREFIX + dest.name, arm=arm, source=source))
    tests = dest / "tests"
    shutil.copytree(FOLLOWUP_DIR / "tests", tests)
    shutil.copytree(SHARED_DIR / "verification", tests / "verification")
    shutil.copy2(SHARED_DIR / "consult_lib.py", tests / "consult_lib.py")
    shutil.copy2(HIDDEN_DIR / f"{TASK}-followup.mjs", tests / "hidden.mjs")
    shutil.copy2(HIDDEN_DIR / f"{TASK}.mjs", tests / "stages.mjs")


def build_tasks(sources: dict[str, Path], scaffold: Path, out: Path) -> list[Path]:
    """One task per passing trial of each arm's job; a trial whose tree cannot be rebuilt is skipped and printed."""
    built = []
    for arm, job in sources.items():
        for trial in passing_trials(job):
            dest = out / task_slug(arm, trial)
            with tempfile.TemporaryDirectory(prefix="consult-followup-") as tmp:
                workspace = Path(tmp) / "app"
                flags = rescore.rebuild(trial, scaffold, workspace)
                if flags:
                    print(f"skipped {job.name}/{trial.name}: {'; '.join(flags)}", flush=True)
                    continue
                write_task(dest, workspace, arm, trial)
            built.append(dest)
    return built


def job_config(out: Path, tasks: list[Path], agent: dict, attempts: int) -> dict:
    """The agent's bare arm, as run.py builds it: each task runs in a fresh session with no skills and no hook."""
    return {
        "job_name": f"{out.name}-followup-{agent['name']}",
        "jobs_dir": str(run.RUNS_DIR),
        "n_attempts": attempts,
        "n_concurrent_trials": 2,
        "tasks": [{"path": str(t)} for t in tasks],
        "agents": [run.arm_agent(agent, [], None, None)],
    }


def build(args: argparse.Namespace) -> int:
    agent, host_env, _ = run.load_agent(args.agent, None)
    sources = {"bare": args.bare_job, "consult": args.consult_job}
    out = OUT_DIR / dt.datetime.now().strftime("%Y-%m-%d__%H-%M-%S")
    with tempfile.TemporaryDirectory(prefix="consult-followup-") as tmp:
        scaffold = rescore.build_scaffolds([TASK], Path(tmp))[TASK]
        tasks = build_tasks(sources, scaffold, out)
    if not tasks:
        print(f"no passing {TASK} trials could be rebuilt", file=sys.stderr)
        return 1
    config_path = out / "job.json"
    config_path.write_text(json.dumps(job_config(out, tasks, agent, args.attempts), indent=2))
    env = " ".join(f"{k}={v}" for k, v in host_env.items())
    print(f"wrote {len(tasks)} tasks under {out}\nrun them with:\n  {env} harbor run -c {config_path} --yes")
    return 0


# ------------------------------------------------------------------- report


def files_touched(bundle_path: Path) -> int | None:
    """Files the diff names plus new files; None without a readable bundle."""
    if not bundle_path.is_file():
        return None
    try:
        bundle = parse_bundle(bundle_path.read_text(errors="replace"))
    except RebuildError:
        return None
    changed = sum(1 for line in bundle.diff.splitlines() if line.startswith("diff --git "))
    return changed + len(bundle.new_files)


def load_arms(job_dir: Path) -> dict[str, list[dict]]:
    """Source arm -> lift.py trial entries, with pass and files touched added to each entry's cost."""
    by_arm: dict[str, list[dict]] = {arm: [] for arm in ARMS}
    for task, entries in lift.load_trials(job_dir).items():
        arm = source_arm(task)
        if arm is None:
            continue
        for entry in entries:
            passed = float(entry["rewards"].get("verification") or 0.0) == 1.0
            bundle = job_dir / entry["trial"] / "verifier" / "judge-bundle.md"
            entry["cost"] = {**entry["cost"], "passed": float(passed), "files_touched": files_touched(bundle)}
            by_arm[arm].append(entry)
    return by_arm


def summarize(by_arm: dict[str, list[dict]]) -> dict[str, dict]:
    """Per metric, each arm's mean, the change (consult-built minus bare-built), and its interval, from lift.py."""
    bare, consult = {TASK: by_arm["bare"]}, {TASK: by_arm["consult"]}
    return {metric: lift.compare_cost(bare, consult, metric) for metric in METRICS}


def render_row(metric: str, result: dict) -> str:
    label, spec = METRICS[metric]
    if result["change"] is None:
        return f"| {label} | - | - | - | no trials recorded it |"
    bounds = result["interval"]
    spread = (
        "no interval: needs 2+ trials per arm and some spread"
        if bounds is None
        else f"{format(bounds[0], '+' + spec)} to {format(bounds[1], '+' + spec)}, {lift.noise_verdict(*bounds)}"
    )
    means = f"{format(result['bare'], spec)} | {format(result['consult'], spec)}"
    return f"| {label} | {means} | {format(result['change'], '+' + spec)} | {spread} |"


def render(summary: dict[str, dict], by_arm: dict[str, list[dict]], job_dir: Path) -> str:
    failed = lift.failed_trials(e for arm in ARMS for e in by_arm[arm])
    lines = [
        f"# Follow-up change: {job_dir.name}",
        "",
        f"Trials: {len(by_arm['bare'])} on trees built by bare, {len(by_arm['consult'])} on trees built by consult.",
        "",
        "| metric | trees by bare | trees by consult | change | 90% interval |",
        "| --- | ---: | ---: | ---: | --- |",
        *(render_row(m, summary[m]) for m in METRICS),
    ]
    if failed:
        lines += ["", f"No reward, counted as a fail: {', '.join(failed)}"]
    return "\n".join(lines) + "\n"


def report(args: argparse.Namespace) -> int:
    by_arm = load_arms(args.job)
    if not any(by_arm.values()):
        print(f"no follow-up trials in {args.job}", file=sys.stderr)
        return 1
    print(render(summarize(by_arm), by_arm, args.job), end="")
    return 0


# ------------------------------------------------------------------- main


def parse_args(argv: Iterable[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)
    build_parser = commands.add_parser("build", help="write the follow-up tasks from two houseStyle jobs")
    build_parser.add_argument("bare_job", type=Path)
    build_parser.add_argument("consult_job", type=Path)
    build_parser.add_argument("--agent", default="claude-code", help="eval/agents/<name>.yaml whose bare arm runs them")
    build_parser.add_argument("--attempts", type=int, default=1, help="Harbor n_attempts per follow-up task")
    report_parser = commands.add_parser("report", help="compare the follow-up job's trials by source arm")
    report_parser.add_argument("job", type=Path)
    return parser.parse_args(list(argv))


def main(argv: list[str]) -> int:
    args = parse_args(argv[1:])
    return build(args) if args.command == "build" else report(args)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
