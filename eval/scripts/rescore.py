#!/usr/bin/env python3
"""Rescore finished Harbor jobs offline against the current task tests.

  uv run --project eval eval/scripts/rescore.py runs/<job> [runs/<job> ...]
                        [--tasks a,b] [--concurrency 4] [--dry-run]

Per trial it rebuilds the final workspace: the task image's /app scaffold
with the final step's judge-bundle.md applied. It then runs the task's current
tests/ in that image as Harbor's shared verifier does, with the final step's
agent logs at /logs/agent and CONSULT_EVAL_SKIP_JUDGE=1, so no model is called.
The judge saw the same bundle, so the trial keeps its original judge score and
the reward is recomputed with the weights in the task's tests/reward.toml. A
multi-step trial's reward is its final step's (multi_step_reward_strategy =
"final"); its first step is copied unchanged.

Output goes to <job>-rescored/, in the layout lift.py reads, with rescore.md
and rescore.json listing old and new values per trial. A trial is not scored
when the original run recorded no reward (a crashed judge leaves no judge
score to keep), when its bundle is missing, truncated, or does not apply,
when a file under the task's environment/ changed after the trial started,
when the verifier fails, or when the verifier's rebuilt judge-bundle.md
differs from the original. Such a trial's result.json carries a RescoreError,
so lift.py lists it as a failed trial. The bundle holds only the agent's
changes, so the bundle comparison cannot see a scaffold edit. The
environment/ check covers that.

--dry-run builds the images, rebuilds every workspace, and prints the flags.
It runs no verifier and writes nothing.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime
from itertools import chain
from pathlib import Path

EVAL_DIR = Path(__file__).resolve().parent.parent
TASKS_DIR = EVAL_DIR / "tasks"
sys.path.insert(0, str(EVAL_DIR / "scripts"))
import lift  # noqa: E402
from bundle import Bundle, RebuildError, parse_bundle  # noqa: E402

HUNK_RE = re.compile(r"^@@ -\d+(?:,(\d+))? \+\d+(?:,(\d+))? @@")
# Host git must ignore the user's config: a global diff or apply setting changes the result.
GIT_ENV = {"GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"}
VERIFIER_ENV = {"CONSULT_EVAL_SKIP_JUDGE": "1"}
# Harbor's build_execution_command for /tests/test.sh with the verifier's stdout path.
VERIFIER_COMMAND = "(/tests/test.sh) > /logs/verifier/test-stdout.txt 2>&1"
VERIFIER_TIMEOUT_SEC = 900
SUMMARY_KEYS = ("verification", "proof", "change_quality", "reward")


class DockerError(RuntimeError):
    pass


@dataclass(frozen=True)
class Trial:
    job: Path
    dir: Path
    task: str
    steps: tuple[str, ...]
    result: dict

    @property
    def name(self) -> str:
        return self.dir.name

    @property
    def final_rel(self) -> Path:
        return Path("steps", self.steps[-1]) if self.steps else Path()

    @property
    def bundle_path(self) -> Path:
        return self.dir / self.final_rel / "verifier" / "judge-bundle.md"

    @property
    def old_rewards(self) -> dict:
        return (self.result.get("verifier_result") or {}).get("rewards") or {}

    @property
    def out_dir(self) -> Path:
        return self.job.with_name(f"{self.job.name}-rescored")


# ------------------------------------------------------------------- bundle

def patch_text(diff: str) -> str:
    """The diff as git printed it: build_bundle strips the final newline and any blank context lines before it."""
    if not diff:
        return ""
    lines = diff.split("\n")
    return "\n".join(lines + [" "] * stripped_context(lines)) + "\n"


def stripped_context(lines: list[str]) -> int:
    """Blank context lines the last hunk lacks against its header counts."""
    start = last_hunk_start(lines)
    if start is None:
        return 0
    match = HUNK_RE.match(lines[start])
    old_count, new_count = int(match.group(1) or 1), int(match.group(2) or 1)
    body = lines[start + 1:]
    missing = old_count - sum(1 for line in body if line[:1] in (" ", "-"))
    new_missing = new_count - sum(1 for line in body if line[:1] in (" ", "+"))
    return missing if missing > 0 and missing == new_missing else 0


def last_hunk_start(lines: list[str]) -> int | None:
    """Index of the last hunk header, or None when the last file in the diff has no hunk."""
    for index in range(len(lines) - 1, -1, -1):
        if lines[index].startswith("diff --git "):
            return None
        if HUNK_RE.match(lines[index]):
            return index
    return None


def git(workspace: Path, *args: str, stdin: str | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(workspace), *args], input=stdin, capture_output=True, text=True,
                          env={**os.environ, **GIT_ENV}, check=False)


def reconstruct(workspace: Path, bundle: Bundle) -> None:
    """Apply the bundle to a checkout of the scaffold commit, as the verifier found it."""
    patch = patch_text(bundle.diff)
    if patch:
        git(workspace, "update-index", "-q", "--refresh")
        # --index: a file the agent added to git shows in the diff, not as untracked.
        applied = git(workspace, "apply", "--index", "--whitespace=nowarn", "-", stdin=patch)
        if applied.returncode:
            raise RebuildError(f"diff does not apply: {applied.stderr.strip()[-300:]}")
    for rel, content in bundle.new_files:
        write_new_file(workspace, rel, content)


def write_new_file(workspace: Path, rel: str, content: str) -> None:
    path = (workspace / rel).resolve()
    if workspace.resolve() not in path.parents:
        raise RebuildError(f"new file outside the workspace: {rel}")
    if path.exists():
        raise RebuildError(f"new file already exists after the diff: {rel}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def original_flags(trial: Trial) -> list[str]:
    """Why the original run cannot be rescored: no bundle, no judge score to keep, or a changed scaffold."""
    if not trial.bundle_path.is_file():
        return ["no judge-bundle.md: the original verifier did not run"]
    if "reward" not in trial.old_rewards:
        error = (trial.result.get("exception_info") or {}).get("exception_type") or "no exception recorded"
        return [f"the original verifier recorded no reward ({error}): there is no judge score to keep"]
    return environment_flags(trial)


def environment_flags(trial: Trial) -> list[str]:
    """The scaffold is built from the current environment/, so a path changed since the trial started may differ."""
    started = trial.result.get("started_at")
    if not started:
        return ["result.json has no started_at: cannot tell whether the task environment changed since the run"]
    environment = TASKS_DIR / trial.task / "environment"
    newest = max(p.lstat().st_mtime for p in [environment, *environment.rglob("*")])
    if newest > datetime.fromisoformat(started.replace("Z", "+00:00")).timestamp():
        return [f"tasks/{trial.task}/environment changed after the trial started: "
                "the scaffold may not be the one the agent saw"]
    return []


def rebuild(trial: Trial, scaffold: Path, workspace: Path) -> list[str]:
    """Rebuild the trial's final workspace from a copy of the scaffold; the flags say why it could not."""
    flags = original_flags(trial)
    if flags:
        return flags
    shutil.copytree(scaffold, workspace, symlinks=True)
    try:
        reconstruct(workspace, parse_bundle(trial.bundle_path.read_bytes().decode("utf-8")))
    except (RebuildError, UnicodeDecodeError) as error:
        return [str(error)]
    return []


def dependency_notes(workspace: Path) -> list[str]:
    """The bundle never carries node_modules, so an agent's npm install is missing from the rebuild."""
    manifest = workspace / "package.json"
    try:
        declared = json.loads(manifest.read_text()) if manifest.is_file() else {}
    except ValueError:
        return []
    if not isinstance(declared, dict) or not (declared.get("dependencies") or declared.get("devDependencies")):
        return []
    return ["package.json declares dependencies and the rebuild has no node_modules: checks that run them may drop"]


# ------------------------------------------------------------------- rewards

def task_weights(task: str) -> dict[str, float]:
    text = (TASKS_DIR / task / "tests" / "reward.toml").read_text()
    return {name: float(w) for name, w in lift.WEIGHT_RE.findall(lift.WEIGHTS_RE.search(text).group(1))}


def weighted_reward(dimensions: dict[str, float], weights: dict[str, float]) -> float:
    """RewardKit's weighted mean over the dimensions present, rounded as it rounds; an unlisted dimension weighs 1."""
    total = sum(weights.get(d, 1.0) for d in dimensions)
    if not total:
        return 0.0
    return round(sum(float(v) * weights.get(d, 1.0) for d, v in dimensions.items()) / total, 4)


def merge_rewards(old: dict, new: dict, weights: dict[str, float]) -> dict:
    """The new deterministic dimensions, the original judge score, and the reward recomputed from both."""
    dimensions = {d: v for d, v in new.items() if d not in ("reward", "judge")}
    if "judge" in old:
        dimensions["judge"] = old["judge"]
    return {**dimensions, "reward": weighted_reward(dimensions, weights)}


def merge_details(old_path: Path, new_path: Path) -> dict:
    new = json.loads(new_path.read_text())
    old = json.loads(old_path.read_text()) if old_path.is_file() else {}
    return {**new, **({"judge": old["judge"]} if "judge" in old else {})}


def merge_final(trial: Trial, verifier_dir: Path) -> dict:
    """Merge the original judge into the new reward.json and reward-details.json; returns the rewards."""
    rewards = merge_rewards(trial.old_rewards, json.loads((verifier_dir / "reward.json").read_text()),
                            task_weights(trial.task))
    details = merge_details(trial.bundle_path.parent / "reward-details.json", verifier_dir / "reward-details.json")
    replace_file(verifier_dir / "reward.json", json.dumps(rewards, indent=2))
    replace_file(verifier_dir / "reward-details.json", json.dumps(details, indent=2))
    return rewards


def replace_file(path: Path, text: str) -> None:
    """Rootful Docker on Linux leaves the verifier files root-owned: the host user can replace them, not write them."""
    staged = path.with_name(f".{path.name}.rescore")
    staged.write_text(text)
    os.replace(staged, path)


# ------------------------------------------------------------------- docker

def docker(*args: str) -> str:
    proc = subprocess.run(["docker", *args], capture_output=True, text=True, check=False)
    if proc.returncode:
        raise DockerError(f"docker {args[0]} failed: {proc.stderr.strip()[-1000:]}")
    return proc.stdout


def image_tag(task: str) -> str:
    return f"consult-rescore/{task}"


def build_scaffold(task: str, dest: Path) -> Path:
    """Build the task image and copy out its /app; environment_flags checks it predates each trial."""
    print(f"building {image_tag(task)}", flush=True)
    docker("build", "-q", "-t", image_tag(task), str(TASKS_DIR / task / "environment"))
    container = docker("create", image_tag(task)).strip()
    try:
        docker("cp", f"{container}:/app", str(dest))
    finally:
        docker("rm", container)
    return dest


def build_scaffolds(tasks: list[str], root: Path) -> dict[str, Path]:
    try:
        return {task: build_scaffold(task, root / task) for task in tasks}
    except DockerError as error:
        raise SystemExit(str(error)) from error


def test_dirs(trial: Trial) -> list[Path]:
    """Harbor uploads the task's tests/, then the final step's own tests/ over it."""
    task_dir = TASKS_DIR / trial.task
    dirs = [task_dir / "tests", *([task_dir / "steps" / trial.steps[-1] / "tests"] if trial.steps else [])]
    return [d for d in dirs if d.is_dir()]


def load_container(name: str, trial: Trial, workspace: Path) -> None:
    docker("exec", name, "sh", "-c", "rm -rf /app && mkdir /app")
    docker("cp", f"{workspace}/.", f"{name}:/app")
    # docker cp keeps the host uid, and git refuses a repository another user owns.
    docker("exec", name, "chown", "-R", "root:root", "/app")
    for tests in test_dirs(trial):
        docker("cp", f"{tests}/.", f"{name}:/tests")
    docker("exec", name, "chmod", "+x", "/tests/test.sh")


def run_container(trial: Trial, workspace: Path, final_dest: Path) -> list[str]:
    """Run the verifier on the rebuilt workspace; outputs land in final_dest/verifier. Returns failure flags."""
    name = f"consult-rescore-{os.getpid()}-{trial.name}"
    logs = final_dest.resolve()
    mounts = ["-v", f"{logs / 'agent'}:/logs/agent", "-v", f"{logs / 'verifier'}:/logs/verifier"]
    env = list(chain.from_iterable(["-e", f"{k}={v}"] for k, v in VERIFIER_ENV.items()))
    try:
        docker("run", "-d", "--name", name, *mounts, image_tag(trial.task), "sleep", "infinity")
        load_container(name, trial, workspace)
        subprocess.run(["docker", "exec", "-w", "/app", *env, name, "bash", "-c", VERIFIER_COMMAND],
                       capture_output=True, timeout=VERIFIER_TIMEOUT_SEC, check=False)
    except DockerError as error:
        return [str(error)]
    except subprocess.TimeoutExpired:
        return [f"verifier timed out after {VERIFIER_TIMEOUT_SEC}s"]
    finally:
        subprocess.run(["docker", "rm", "-f", name], capture_output=True, check=False)
    return []


def verifier_flags(trial: Trial, verifier_dir: Path) -> list[str]:
    """The verifier scored, and the bundle it rebuilt matches the one the judge read."""
    if not (verifier_dir / "reward.json").is_file():
        return ["verifier wrote no reward.json; see test-stdout.txt"]
    rebuilt = verifier_dir / "judge-bundle.md"
    if not rebuilt.is_file() or rebuilt.read_bytes() != trial.bundle_path.read_bytes():
        return ["rebuilt judge-bundle.md differs from the original: the workspace is not the one judged"]
    return []


# ------------------------------------------------------------------- trials

def load_trial(trial_dir: Path) -> Trial:
    result = json.loads((trial_dir / "result.json").read_text())
    task = (result.get("task_name") or trial_dir.name.split("__")[0]).split("/")[-1]
    steps = tuple(s["step_name"] for s in result.get("step_results") or [])
    return Trial(job=trial_dir.parent, dir=trial_dir, task=task, steps=steps, result=result)


def load_job(job_dir: Path, tasks: set[str]) -> list[Trial]:
    trials = [load_trial(p.parent) for p in sorted(job_dir.glob("*/result.json"))]
    return [t for t in trials if not tasks or t.task in tasks]


def copy_trial(trial: Trial, dest: Path) -> Path:
    """Copy the trial to dest with an empty final verifier dir; returns the final step's dir under dest."""
    shutil.rmtree(dest, ignore_errors=True)
    shutil.copytree(trial.dir, dest, symlinks=True)
    final_dest = dest / trial.final_rel
    shutil.rmtree(final_dest / "verifier", ignore_errors=True)
    (final_dest / "verifier").mkdir(parents=True)
    (final_dest / "agent").mkdir(exist_ok=True)
    return final_dest


def verify(trial: Trial, scaffold: Path, final_dest: Path) -> tuple[list[str], list[str]]:
    """(flags that stop the trial being scored, notes on checks the rebuild may not reproduce)."""
    with tempfile.TemporaryDirectory(prefix="consult-rescore-") as tmp:
        workspace = Path(tmp) / "app"
        flags = rebuild(trial, scaffold, workspace)
        if flags:
            return flags, []
        notes = dependency_notes(workspace)
        flags = run_container(trial, workspace, final_dest)
    return flags or verifier_flags(trial, final_dest / "verifier"), notes


def rescored_result(result: dict, record: dict) -> dict:
    """result.json with the merged rewards, or a RescoreError when the trial was not scored."""
    verifier = {"rewards": record["new"]} if record["new"] is not None else None
    out = {**result, "verifier_result": verifier, "rescore": record}
    if verifier is None:
        out["exception_info"] = {"exception_type": "RescoreError", "exception_message": "; ".join(record["flags"])}
    if result.get("step_results"):
        steps = result["step_results"]
        out["step_results"] = [*steps[:-1], {**steps[-1], "verifier_result": verifier}]
    return out


def rescore_trial(trial: Trial, scaffold: Path) -> dict:
    dest = trial.out_dir / trial.name
    final_dest = copy_trial(trial, dest)
    flags, notes = verify(trial, scaffold, final_dest)
    record = {"old": trial.old_rewards, "new": None if flags else merge_final(trial, final_dest / "verifier"),
              "flags": flags, "notes": notes}
    (dest / "result.json").write_text(json.dumps(rescored_result(trial.result, record), indent=4))
    print(f"{trial.job.name}/{trial.name}: {row_text(record)}", flush=True)
    return record


def dry_run_trial(trial: Trial, scaffold: Path) -> list[str]:
    with tempfile.TemporaryDirectory(prefix="consult-rescore-") as tmp:
        workspace = Path(tmp) / "app"
        flags = rebuild(trial, scaffold, workspace)
        notes = [] if flags else dependency_notes(workspace)
    print(f"{trial.job.name}/{trial.name}: {'; '.join(flags + notes) or 'rebuilds cleanly'}", flush=True)
    return flags


# ------------------------------------------------------------------- summary

def value_pair(record: dict, key: str) -> str:
    old, new = record["old"].get(key), (record["new"] or {}).get(key)
    return " -> ".join("-" if v is None else f"{float(v):.3f}" for v in (old, new))


def row_text(record: dict) -> str:
    return "; ".join(record["flags"]) or "; ".join([f"reward {value_pair(record, 'reward')}", *record["notes"]])


def summary_rows(out_dir: Path) -> list[dict]:
    """Every rescored trial under out_dir, including ones an earlier --tasks run wrote."""
    rows = []
    for path in sorted(out_dir.glob("*/result.json")):
        result = json.loads(path.read_text())
        rows.append({"trial": path.parent.name, "task": result.get("task_name"), **result["rescore"]})
    return rows


def summary_line(row: dict) -> str:
    values = " | ".join(value_pair(row, k) for k in SUMMARY_KEYS)
    return f"| {row['trial']} | {values} | {'; '.join(row['flags'])} | {'; '.join(row.get('notes') or [])} |"


def render_summary(summary: dict) -> str:
    rows = summary["trials"]
    lines = [f"# Rescore: {Path(summary['job']).name}", "",
             "Deterministic dimensions rerun with the current task tests; judge scores are the originals.", "",
             f"| trial | {' | '.join(SUMMARY_KEYS)} | flags | notes |",
             f"| --- |{' ---: |' * len(SUMMARY_KEYS)} --- | --- |", *map(summary_line, rows)]
    scored = [r for r in rows if r["new"] is not None]
    changed = [r for r in scored if abs(float(r["new"]["reward"]) - float(r["old"].get("reward") or 0.0)) > 0.001]
    lines += ["", f"Scored {len(scored)} of {len(rows)} trials; {len(changed)} changed reward by more than 0.001."]
    return "\n".join(lines) + "\n"


def write_summary(out_dir: Path, job: Path) -> str:
    summary = {"job": str(job), "rescored": str(out_dir), "trials": summary_rows(out_dir)}
    markdown = render_summary(summary)
    (out_dir / "rescore.json").write_text(json.dumps(summary, indent=2))
    (out_dir / "rescore.md").write_text(markdown)
    return markdown


# ------------------------------------------------------------------- main

def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("jobs", nargs="+", type=Path, help="Harbor job dirs")
    parser.add_argument("--tasks", default="", help="comma-separated task names (default: all)")
    parser.add_argument("--concurrency", type=int, default=4)
    parser.add_argument("--dry-run", action="store_true",
                        help="rebuild the workspaces and print flags; run no verifier")
    return parser.parse_args(argv)


def select_trials(args: argparse.Namespace) -> list[Trial]:
    tasks = {t.strip() for t in args.tasks.split(",") if t.strip()}
    unknown = sorted(t for t in tasks if not (TASKS_DIR / t / "tests").is_dir())
    if unknown:
        raise SystemExit(f"--tasks names no task under {TASKS_DIR}: {', '.join(unknown)}")
    trials = list(chain.from_iterable(load_job(job, tasks) for job in dict.fromkeys(args.jobs)))
    if not trials:
        raise SystemExit("no trials to rescore")
    return trials


def rescore(trials: list[Trial], scaffolds: dict[str, Path], concurrency: int) -> int:
    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        records = list(pool.map(lambda t: rescore_trial(t, scaffolds[t.task]), trials))
    for out_dir, job in {t.out_dir: t.job for t in trials}.items():
        print(f"\n{write_summary(out_dir, job)}{out_dir}", flush=True)
    return 1 if any(r["flags"] for r in records) else 0


def main(argv: list[str]) -> int:
    args = parse_args(argv[1:])
    trials = select_trials(args)
    with tempfile.TemporaryDirectory(prefix="consult-rescore-") as tmp:
        scaffolds = build_scaffolds(sorted({t.task for t in trials}), Path(tmp))
        if args.dry_run:
            flagged = [t for t in trials if dry_run_trial(t, scaffolds[t.task])]
            return 1 if flagged else 0
        return rescore(trials, scaffolds, args.concurrency)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
