#!/usr/bin/env python3
"""Run a Consult suite through Harbor with and without Consult skills, then report lift.

Examples:
  uv run scripts/run.py --suite smoke --agent claude-code --arms bare,consult
  uv run scripts/run.py --suite core --agent claude-code --arms bare,stub,consult
  uv run scripts/run.py --suite core --agent codex --arms consult --attempts 3
  uv run scripts/run.py --suite smoke --agent claude-code --install-only
  uv run scripts/run.py --suite rules --agent claude-code --preflight-only --effort high
  uv run scripts/run.py --tier release --agent claude-code
  uv run scripts/run.py --tier fast --changed-since HEAD

One Harbor job is written and started per arm. The consult arm adds a snapshot
of the canonical skills directory (agents/.agents/skills), copied under
runs/consult-skills/ when the run starts, so a skill edit during the run
reaches no arm. The bare arm is the same agent with no skills. The stub arm
adds stub skills that stub.py builds from that snapshot under
runs/stub-skills/: the same names and descriptions with neutral bodies. It gets
the same hook as the consult arm, so it differs from consult only in skill
content and from bare only in the listing and hook. Job configs and results
land under eval/runs/.

Before the arms, a preflight runs each task's first turn in the consult arm with
verification off and reports which Consult skills the agent loaded. The run
stops when the share of preflight trials that loaded any skill is below
--preflight-min, because the consult arm would then measure the bare agent.

Tiers are presets:
  release  engineeringMaturity + rules, bare, stub, and consult arms, 3 attempts,
           judge on; saves the baseline release-<agent>. Run it once per agent
           before a release.
  fast     claude-code, the tasks that exercise the skills changed since
           --changed-since (at most --max-tasks, else the core suite), consult
           arm only, 3 attempts, no judge. It reuses the bare arm of baseline
           release-claude-code and compares against that baseline's Consult
           arm. It catches skill-loading failures and large regressions, not
           small ones: read the intervals in the lift report.
A baseline is reused only when agent, model, effort, CLI version, and every
task dir match; otherwise the bare arm runs and the reason is printed.

--drop-references code-review,security runs the consult arm without those
skills' references/ dirs. It needs --tier fast and a reusable baseline whose
consult arm ran today's full pack, so the lift report's comparison against
that arm is the full pack against the ablation and nothing else. An ablation
never saves a baseline.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import subprocess
import sys
from itertools import chain
from pathlib import Path

import baseline
import preflight
import selection
import stub

EVAL_DIR = Path(__file__).resolve().parent.parent
REPO_DIR = EVAL_DIR.parent
SKILLS_DIR = REPO_DIR / "agents" / ".agents" / "skills"
RUNS_DIR = EVAL_DIR / "runs"
ARMS = ("bare", "stub", "consult")
RELEASE_SUITES = ("engineeringMaturity", "rules")


def read_yaml(path: Path) -> dict:
    import yaml  # here, not at the top, so the tests import this module with the standard library only

    return yaml.safe_load(path.read_text())


def load_suite(name: str) -> list[str]:
    path = EVAL_DIR / "suites" / f"{name}.yaml"
    if not path.is_file():
        raise SystemExit(f"unknown suite {name!r}; expected {path}")
    trials = read_yaml(path).get("trials") or []
    missing = [t for t in trials if not (EVAL_DIR / "tasks" / t / "task.toml").is_file()]
    if missing:
        raise SystemExit(f"suite {name} lists tasks without a Harbor task dir: {', '.join(missing)}")
    return trials


def load_agent(name: str, model: str | None) -> tuple[dict, dict[str, str], dict | None]:
    """Agent fragment, host_env (variables exported to the harbor process), and hook settings.

    Auth toggles such as CODEX_FORCE_AUTH_JSON stay out of the job config on
    purpose. Harbor scrubs the value of every AUTH/TOKEN-named agent env var from
    the persisted trial files, so a literal "1" there corrupts trajectory.json.

    `consult_settings` names a repo file whose JSON the consult and stub arms pass
    as the agent's native settings. Claude Code uses it to install the plugin's
    SessionStart hook, which Harbor's plain skill injection would otherwise skip.
    """
    path = EVAL_DIR / "agents" / f"{name}.yaml"
    if not path.is_file():
        raise SystemExit(f"unknown agent {name!r}; expected {path}")
    agent = read_yaml(path)
    host_env = {k: str(v) for k, v in (agent.pop("host_env", None) or {}).items()}
    settings_path = agent.pop("consult_settings", None)
    settings = json.loads((REPO_DIR / settings_path).read_text()) if settings_path else None
    if model:
        agent["model_name"] = model
    return agent, host_env, settings


def frozen_skills(drop_references: tuple[str, ...] = ()) -> dict[str, list[str]]:
    """arm -> skills dirs it installs, from one snapshot of SKILLS_DIR taken now and read by every later trial.

    drop_references leaves those skills' references/ out of the consult arm only.
    """
    real = stub.snapshot(SKILLS_DIR, RUNS_DIR / "consult-skills")
    consult = stub.snapshot(real, RUNS_DIR / "consult-skills", drop_references) if drop_references else real
    return {"bare": [], "stub": [str(stub.build(real, RUNS_DIR / "stub-skills"))], "consult": [str(consult)]}


def arm_agent(agent: dict, skills: list[str], settings: dict | None, effort: str | None) -> dict:
    """Every arm with skills gets the hook settings, so stub and consult differ only in skill bodies."""
    agent = dict(agent)
    agent["skills"] = skills
    kwargs = dict(agent.get("kwargs", {}))
    if agent["skills"] and settings:
        kwargs["config"] = settings
    if effort:
        kwargs["reasoning_effort"] = effort
    agent["kwargs"] = kwargs
    return agent


def job_label(args: argparse.Namespace) -> str:
    label = f"{args.suite or args.tier}-{args.agent}" + (f"-{args.effort}" if args.effort else "")
    return label + (f"-norefs-{'+'.join(args.drop_references)}" if args.drop_references else "")


def release_tasks() -> list[str]:
    return list(dict.fromkeys(t for suite in RELEASE_SUITES for t in load_suite(suite)))


def tier_tasks(args: argparse.Namespace) -> list[str]:
    if args.tier == "release":
        return release_tasks()
    if args.tier == "fast" and not args.suite:
        skills = selection.changed_skills(args.changed_since)
        candidates = release_tasks()
        tasks = selection.select_tasks(skills, candidates, args.max_tasks)
        print(f"fast tier: skills changed since {args.changed_since}: {', '.join(sorted(skills)) or 'none'}; "
              f"tasks: {', '.join(tasks) or 'none, using the core suite'}", flush=True)
        return tasks or load_suite("core")
    return load_suite(args.suite)


def apply_tier(args: argparse.Namespace) -> None:
    """Fill the preset values a tier sets, leaving explicit flags alone."""
    if args.attempts is None:
        args.attempts = 3 if args.tier else 1
    if args.tier and not args.baseline and not args.save_baseline:
        name = f"release-{args.agent}"
        args.baseline, args.save_baseline = (name, None) if args.tier == "fast" else (None, name)
    if args.arms is None:
        args.arms = "bare,stub,consult" if args.tier == "release" else "bare,consult"
    if args.tier == "fast":
        args.arms = "consult"
        args.harbor_args = [*args.harbor_args, "--ve", "CONSULT_EVAL_SKIP_JUDGE=1"]


def reusable_baseline(name: str | None, key: dict) -> dict | None:
    """The stored baseline when its key covers this run, else None with the reason printed."""
    if not name:
        return None
    stored = baseline.load(name)
    reason = "no baseline saved under that name" if stored is None else baseline.mismatch(stored["key"], key)
    if reason:
        print(f"baseline {name}: not reused, {reason}; running the bare arm", flush=True)
        return None
    print(f"baseline {name}: reusing bare job {stored['bare']}", flush=True)
    return stored


def plan_arms(requested: list[str], reuse: dict | None, needs_lift: bool) -> list[str]:
    """A reused baseline replaces the bare arm; without one, lift needs the bare arm to run."""
    if reuse:
        return [a for a in requested if a != "bare"]
    if needs_lift and "bare" not in requested:
        return ["bare", *requested]
    return requested


def build_job(args: argparse.Namespace, arm: str, stamp: str, tasks: list[str], agent: dict, settings: dict | None,
              skills: dict[str, list[str]]) -> dict:
    return {
        "job_name": f"{stamp}-{job_label(args)}-{arm}",
        "jobs_dir": str(RUNS_DIR),
        "n_attempts": args.attempts,
        "n_concurrent_trials": args.concurrency,
        "install_only": bool(args.install_only),
        "tasks": [{"path": str(EVAL_DIR / "tasks" / t)} for t in tasks],
        "agents": [arm_agent(agent, skills[arm], settings, args.effort)],
    }


def run_preflight(args, stamp: str, tasks: list[str], agent: dict, settings: dict | None, host_env: dict,
                  skills: dict[str, list[str]]) -> float:
    """Consult arm, first turn of each task, no verification; returns the share of trials that loaded a skill."""
    task_root = RUNS_DIR / "preflight-tasks" / stamp
    for task in tasks:
        preflight.first_turn_task(EVAL_DIR / "tasks" / task, task_root / task)
    config = {
        "job_name": f"{stamp}-{job_label(args)}-preflight",
        "jobs_dir": str(RUNS_DIR),
        "n_attempts": args.preflight_attempts,
        "n_concurrent_trials": args.concurrency,
        "tasks": [{"path": str(task_root / t)} for t in tasks],
        "agents": [arm_agent(agent, skills["consult"], settings, args.effort)],
        "verifier": {"disable": True},
    }
    config_path = RUNS_DIR / f"{config['job_name']}.job.json"
    config_path.write_text(json.dumps(config, indent=2))
    rows = preflight.loading_rows(start_job(config_path, args.harbor_args, host_env))
    print("\n## Preflight: consult-arm skill loading\n\n" + preflight.render(rows) + "\n", flush=True)
    return preflight.loading_rate(rows)


def preflight_gate(args: argparse.Namespace, rate: float) -> int | None:
    """Exit code that ends the run after the preflight, or None to go on to the arms."""
    if args.preflight_only:
        return 0
    if rate < args.preflight_min:
        print(f"preflight: loading rate {rate:.0%} is below --preflight-min {args.preflight_min:.0%}; "
              "not running the arms (pass --skip-preflight to override)", file=sys.stderr)
        return 3
    return None


def start_job(config_path: Path, extra: list[str], host_env: dict[str, str]) -> Path:
    cmd = ["harbor", "run", "-c", str(config_path), "--yes", *extra]
    print("+", " ".join(f"{k}={v}" for k, v in host_env.items()), " ".join(cmd), flush=True)
    subprocess.run(cmd, check=True, env={**os.environ, **host_env})
    config = json.loads(config_path.read_text())
    return RUNS_DIR / config["job_name"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--suite", help="name of a file under eval/suites/; required without --tier")
    parser.add_argument("--agent", help="name of a file under eval/agents/; the fast tier defaults to claude-code")
    parser.add_argument("--tier", choices=("fast", "release"), help="preset run shape; see the tiers above")
    parser.add_argument("--arms", help="subset of bare,stub,consult (default bare,consult, all three for --tier release)")
    parser.add_argument("--model", help="override the agent fragment's model_name")
    parser.add_argument("--attempts", type=int, help="Harbor n_attempts per task (default 1, or 3 with --tier)")
    parser.add_argument("--concurrency", type=int, default=2, help="Harbor n_concurrent_trials")
    parser.add_argument("--install-only", action="store_true", help="agent setup only; proves wiring and auth")
    parser.add_argument("--no-lift", action="store_true", help="skip the lift report")
    parser.add_argument("--effort", choices=("low", "medium", "high", "xhigh", "max"),
                        help="override the agent fragment's reasoning_effort")
    parser.add_argument("--baseline", help="reuse the bare arm of runs/baselines/<name>.json when it matches")
    parser.add_argument("--save-baseline", help="after the arms run, save them as runs/baselines/<name>.json")
    parser.add_argument("--changed-since", default="HEAD", help="fast tier: git ref to diff the skills against")
    parser.add_argument("--max-tasks", type=int, default=4, help="fast tier: most tasks to select")
    parser.add_argument("--drop-references", default="",
                        help="comma-separated skills whose references/ the consult arm leaves out (an ablation)")
    parser.add_argument("--skip-preflight", action="store_true", help="run the arms without the skill-loading preflight")
    parser.add_argument("--preflight-only", action="store_true", help="run the skill-loading preflight and stop")
    parser.add_argument("--preflight-attempts", type=int, default=1, help="preflight trials per task")
    parser.add_argument("--preflight-min", type=float, default=0.5,
                        help="minimum share of preflight trials that must load a Consult skill")
    parser.add_argument("harbor_args", nargs="*", help="extra args passed to `harbor run` after --")
    args = parser.parse_args()
    if args.tier == "fast":
        args.agent = args.agent or "claude-code"
    if not args.agent or not (args.suite or args.tier):
        parser.error("--agent and one of --suite or --tier are required")
    args.user_harbor_args = list(args.harbor_args)
    apply_tier(args)
    args.drop_references = tuple(sorted(s.strip() for s in args.drop_references.split(",") if s.strip()))
    check_ablation(parser, args)
    return args


def check_ablation(parser: argparse.ArgumentParser, args: argparse.Namespace) -> None:
    """An ablation names skills that have references and never replaces a baseline."""
    if not args.drop_references:
        return
    with_references = {p.parent.name for p in SKILLS_DIR.glob("*/references") if p.is_dir()}
    unknown = [s for s in args.drop_references if s not in with_references]
    if unknown:
        parser.error(f"--drop-references names no skill with a references/ dir: {', '.join(unknown)}")
    if args.save_baseline:
        parser.error("an ablation never saves a baseline; run it with --tier fast, which reuses the saved one")


def ablation_gate(args: argparse.Namespace, reuse: dict | None) -> int | None:
    """Exit code that stops an ablation whose comparison would measure more than the dropped references."""
    if not args.drop_references:
        return None
    if not reuse:
        print("--drop-references compares against a saved baseline's consult arm, and none is reusable",
              file=sys.stderr)
        return 2
    full_pack = str(stub.snapshot(SKILLS_DIR, RUNS_DIR / "consult-skills"))
    baseline_pack = trial_skills_dir(Path(reuse["consult"]))
    if baseline_pack != full_pack:
        print(f"the baseline's consult arm ran {baseline_pack}, not today's full pack {full_pack}; the ablation "
              "would also measure the skill edits since then", file=sys.stderr)
        return 2
    return None


def trial_skills_dir(job_dir: Path) -> str | None:
    """The skills dir a job's agent ran, from Harbor's record of its first trial's config."""
    result = next(iter(sorted(job_dir.glob("*/result.json"))), None)
    if result is None:
        return None
    skills = ((json.loads(result.read_text()).get("config") or {}).get("agent") or {}).get("skills") or []
    return str(skills[0]) if skills else None


def report(args, job_dirs: dict[str, Path], reuse: dict | None, key: dict) -> int:
    bare_dir = job_dirs.get("bare") or (Path(reuse["bare"]) if reuse else None)
    if args.save_baseline and {"bare", "consult"} <= set(job_dirs) and not args.install_only:
        save_baseline(args.save_baseline, key, job_dirs)
    if args.no_lift or args.install_only or bare_dir is None or "consult" not in job_dirs:
        for arm, job_dir in job_dirs.items():
            print(f"{arm}: {job_dir}")
        return 0
    cmd = [sys.executable, str(EVAL_DIR / "scripts" / "lift.py"), str(bare_dir), str(job_dirs["consult"])]
    if reuse:
        cmd += ["--baseline-consult", reuse["consult"]]
    if "stub" in job_dirs:
        cmd += ["--stub", str(job_dirs["stub"])]
    return subprocess.run(cmd).returncode


def save_baseline(name: str, key: dict, job_dirs: dict[str, Path]) -> None:
    """Save only when bare and consult are complete: a trial without a reward would score 0 in every later comparison."""
    # A dry run or a job Harbor never started leaves no trials, which unrewarded_trials cannot see.
    empty = [arm for arm in ("bare", "consult") if not any(job_dirs[arm].glob("*/result.json"))]
    if empty:
        print(f"baseline {name} not saved: no trials in {', '.join(empty)}", file=sys.stderr)
        return
    missing = list(chain.from_iterable(baseline.unrewarded_trials(job_dirs[arm]) for arm in ("bare", "consult")))
    if missing:
        print(f"baseline {name} not saved: no reward for {', '.join(missing)}", file=sys.stderr)
        return
    path = baseline.save(name, key, job_dirs["bare"], job_dirs["consult"], complete_stub(name, job_dirs.get("stub")))
    print(f"saved baseline {path}")


def complete_stub(name: str, stub_dir: Path | None) -> Path | None:
    """The stub job when every trial has a reward; nothing reuses it, so an incomplete one is left out, not blocking."""
    missing = baseline.unrewarded_trials(stub_dir) if stub_dir else []
    if missing:
        print(f"baseline {name}: stub job left out, no reward for {', '.join(missing)}", file=sys.stderr)
        return None
    return stub_dir


def main() -> int:
    args = parse_args()
    requested = [a.strip() for a in args.arms.split(",") if a.strip()]
    unknown = [a for a in requested if a not in ARMS]
    if unknown:
        raise SystemExit(f"unknown arms {unknown}; choose from {ARMS}")

    tasks = tier_tasks(args)
    agent, host_env, settings = load_agent(args.agent, args.model)
    key = baseline.baseline_key(agent, args.effort, tasks, args.user_harbor_args)
    reuse = None if args.install_only else reusable_baseline(args.baseline, key)
    arms = plan_arms(requested, reuse, needs_lift="consult" in requested and not (args.no_lift or args.install_only))
    stamp = dt.datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    skills = frozen_skills(args.drop_references)
    stop = ablation_gate(args, reuse)
    if stop is not None:
        return stop

    if "consult" in arms and not (args.skip_preflight or args.install_only):
        stop = preflight_gate(args, run_preflight(args, stamp, tasks, agent, settings, host_env, skills))
        if stop is not None:
            return stop

    job_dirs: dict[str, Path] = {}
    for arm in arms:
        config = build_job(args, arm, stamp, tasks, agent, settings, skills)
        config_path = RUNS_DIR / f"{config['job_name']}.job.json"
        config_path.write_text(json.dumps(config, indent=2))
        job_dirs[arm] = start_job(config_path, args.harbor_args, host_env)
    return report(args, job_dirs, reuse, key)


if __name__ == "__main__":
    raise SystemExit(main())
