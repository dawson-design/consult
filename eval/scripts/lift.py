#!/usr/bin/env python3
"""Compare a bare Harbor job with a Consult job and report per-task lift.

  uv run scripts/lift.py runs/<bare-job> runs/<consult-job> [--baseline-consult runs/<earlier-consult-job>]
                        [--stub runs/<stub-job>]

Lift = mean Consult reward - mean bare reward per task, over the tasks the
Consult job ran. Trials without a reward (agent or verifier failure) count as
0 and are listed separately. Writes runs/lift/<consult-job-name>.json and .md
next to the table it prints.

Consult aims to raise the floor, so each arm also reports its floor rate: the
share of trials that failed verification or scored below FLOOR_REWARD. Suite
lift and floor-rate change carry a 90% bootstrap interval over trials
resampled within each task. An interval that contains 0 is reported as not
distinguishable from noise. --baseline-consult adds the same comparison
between an earlier Consult job and this one, which catches a skill edit that
made things worse.

--stub adds two comparisons from a stub-arm job, which has Consult's skill
names and descriptions with neutral bodies and the same hook. Consult vs stub
isolates skill content. Stub vs bare isolates the listing and hook. Each shows
per-task rows and the suite reward and floor-rate change with intervals, and
lists the failed trials of both jobs it compares. The skill-content section
ends with a verdict on whether Consult beats the stub with an interval that
excludes 0. A failed trial in either job withholds the verdict, since a gap
from timeouts or auth failures is not a skill-content effect.

The fast tier runs without the judge. When one job has judge scores and the
other does not, both are rescored from their shared deterministic dimensions
with the weights in verifier/shared/reward.<kind>.toml, renormalized as
RewardKit's weighted mean does.

Two scorecards follow the lift table:
  rules   per-rule pass rate per arm, from each trial's reward-details.json
          (`rules` criteria, plus the step-1 `signoff` criteria of a multi-step
          task, which count only when the build step's verification passed)
  skills  per task, the Consult arm's intended skills it read (fired), missed,
          and expect_silent skills it read anyway, from the agent trajectory;
          plus each arm's step-1 sign-off mode (stopped / provisional / built)
"""

from __future__ import annotations

import argparse
import json
import random
import re
import statistics
import sys
from collections import Counter, defaultdict
from collections.abc import Iterable
from itertools import chain
from pathlib import Path

EVAL_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(EVAL_DIR / "verifier" / "shared"))
import consult_lib as cl  # noqa: E402

MODES = ("stopped", "provisional", "built")
READOUTS = ("skill_triggering", "non_interruption")
DIMENSIONS = ("verification", "proof", "change_quality", "no_file_writes", "judge")
FLOOR_REWARD = 0.5
BOOTSTRAP_ROUNDS = 2000
WEIGHTS_RE = re.compile(r"^weights\s*=\s*\{(.*)\}", re.MULTILINE)
WEIGHT_RE = re.compile(r"(\w+)\s*=\s*([0-9.]+)")
JUDGE_EXCLUDED_NOTE = "Rewards exclude the judge: one job ran without it, so both are scored on deterministic dimensions."


def load_trials(job_dir: Path) -> dict[str, list[dict]]:
    """task name -> list of reward dicts (one per attempt)."""
    by_task: dict[str, list[dict]] = defaultdict(list)
    for result_path in sorted(job_dir.glob("*/result.json")):
        result = json.loads(result_path.read_text())
        task = result.get("task_name") or result_path.parent.name.split("__")[0]
        verifier = result.get("verifier_result") or {}
        rewards = verifier.get("rewards") or {}
        entry = {"reward": rewards.get("reward"), "rewards": rewards, "trial": result_path.parent.name}
        if result.get("exception_info"):
            entry["error"] = result["exception_info"].get("exception_type") or "error"
        entry.update(trial_evidence(result_path.parent, result, rewards))
        by_task[task].append(entry)
    return by_task


def trial_evidence(trial_dir: Path, result: dict, rewards: dict) -> dict:
    """Rule scores, sign-off mode, and skills read for one trial, single- or multi-step."""
    steps = [s["step_name"] for s in result.get("step_results") or []]
    final_dir = trial_dir / "steps" / steps[-1] if steps else trial_dir
    rules = criteria(final_dir / "verifier" / "reward-details.json", "rules")
    rules.pop("no_rules", None)
    signoff = criteria(trial_dir / "steps" / steps[0] / "verifier" / "reward-details.json", "signoff") if steps else {}
    built_ok = float(rewards.get("verification") or 0.0) == 1.0
    mode = next((m for m in MODES if signoff.get(f"mode_{m}") == 1.0), None)
    rules.update({k: (v if built_ok else 0.0) for k, v in signoff.items() if not k.startswith("mode_")})
    trajectory = cl.load_trajectory(final_dir / "agent" / "trajectory.json")
    return {"rules": rules, "signoff_mode": mode, "skills_read": cl.read_skill_names(trajectory)}


def criteria(details_path: Path, dimension: str) -> dict[str, float]:
    if not details_path.is_file():
        return {}
    node = json.loads(details_path.read_text()).get(dimension) or {}
    return {c["name"]: float(c["value"]) for c in node.get("criteria") or []}


def task_meta(task: str) -> dict:
    path = EVAL_DIR / "tasks" / task.split("/")[-1] / "tests" / "consult.json"
    return json.loads(path.read_text()) if path.is_file() else {}


def mean_reward(entries: list[dict], key: str) -> float:
    values = [float(e["rewards"].get(key) or 0.0) for e in entries]
    return statistics.fmean(values) if values else 0.0


def below_floor(entry: dict) -> bool:
    """The trial failed its verification checks or its reward is under FLOOR_REWARD."""
    rewards = entry["rewards"]
    failed_checks = "verification" in rewards and float(rewards["verification"] or 0.0) < 1.0
    return failed_checks or float(entry["reward"] or 0.0) < FLOOR_REWARD


def floor_rate(entries: list[dict]) -> float:
    return statistics.fmean(below_floor(e) for e in entries) if entries else 0.0


def percentile(values: list[float], q: float) -> float:
    """Nearest-rank percentile; 0.0 for no values."""
    ordered = sorted(values)
    return ordered[round(q * (len(ordered) - 1))] if ordered else 0.0


def low_tail(entries: list[dict]) -> float:
    return percentile([float(e["reward"] or 0.0) for e in entries], 0.25)


def suite_delta(before: dict[str, list[dict]], after: dict[str, list[dict]], tasks: list[str]) -> tuple[float, float]:
    """(mean reward change, mean floor-rate change) across tasks, each task weighted equally."""
    reward = statistics.fmean(mean_reward(after.get(t, []), "reward") - mean_reward(before.get(t, []), "reward") for t in tasks)
    floor = statistics.fmean(floor_rate(after.get(t, [])) - floor_rate(before.get(t, [])) for t in tasks)
    return reward, floor


def resample(by_task: dict[str, list[dict]], tasks: list[str], rng: random.Random) -> dict[str, list[dict]]:
    return {t: rng.choices(by_task[t], k=len(by_task[t])) for t in tasks if by_task.get(t)}


def compare(before: dict[str, list[dict]], after: dict[str, list[dict]], seed: int = 0) -> dict:
    """Suite reward and floor-rate change over the tasks both jobs ran, with 90% bootstrap intervals.

    Tasks the before job lacks are left out and listed, not scored as 0. The
    intervals are None when resampling cannot estimate spread (see estimable).
    """
    tasks = sorted(t for t in after if before.get(t) and after[t])
    result = {"tasks": tasks, "missing": sorted(t for t in after if not before.get(t)),
              "reward": 0.0, "floor_rate": 0.0, "reward_interval": None, "floor_rate_interval": None}
    if not tasks:
        return result
    result["reward"], result["floor_rate"] = suite_delta(before, after, tasks)
    if estimable(before, after, tasks):
        rng = random.Random(seed)
        draws = [suite_delta(resample(before, tasks, rng), resample(after, tasks, rng), tasks) for _ in range(BOOTSTRAP_ROUNDS)]
        result["reward_interval"] = interval([d[0] for d in draws])
        result["floor_rate_interval"] = interval([d[1] for d in draws])
    return result


def estimable(before: dict[str, list[dict]], after: dict[str, list[dict]], tasks: list[str]) -> bool:
    """Every task has 2+ trials per arm and some task varies; otherwise the interval collapses to the point."""
    arms = [by_task[t] for by_task in (before, after) for t in tasks]
    if any(len(entries) < 2 for entries in arms):
        return False
    return any(len({float(e["reward"] or 0.0) for e in entries}) > 1 for entries in arms)


def interval(values: list[float]) -> tuple[float, float]:
    return percentile(values, 0.05), percentile(values, 0.95)


def reward_weights(kind: str) -> dict[str, float]:
    text = (EVAL_DIR / "verifier" / "shared" / f"reward.{kind}.toml").read_text()
    return {name: float(w) for name, w in WEIGHT_RE.findall(WEIGHTS_RE.search(text).group(1))}


def has_judge(by_task: dict[str, list[dict]]) -> bool:
    return any("judge" in e["rewards"] for e in chain.from_iterable(by_task.values()))


def without_judge(task: str, entries: list[dict]) -> list[dict]:
    """Entries with reward recomputed as the weighted mean of their non-judge dimensions."""
    weights = reward_weights(task_meta(task).get("kind") or "code")
    return [rescored(e, deterministic_reward(e["rewards"], weights)) for e in entries]


def rescored(entry: dict, reward: float | None) -> dict:
    rewards = {k: v for k, v in entry["rewards"].items() if k != "judge"}
    return {**entry, "reward": reward, "rewards": {**rewards, "reward": reward}}


def deterministic_reward(rewards: dict, weights: dict[str, float]) -> float | None:
    scored = {d: w for d, w in weights.items() if w > 0 and d != "judge" and d in rewards}
    if not scored:
        return None
    return sum(float(rewards[d] or 0.0) * w for d, w in scored.items()) / sum(scored.values())


def align(before: dict[str, list[dict]], after: dict[str, list[dict]]) -> tuple[dict, dict, bool]:
    """Both jobs rescored without the judge when only one has judge scores; the flag says so."""
    if has_judge(before) == has_judge(after):
        return before, after, False
    return strip_judge(before), strip_judge(after), True


def strip_judge(by_task: dict[str, list[dict]]) -> dict[str, list[dict]]:
    return {t: without_judge(t, entries) for t, entries in by_task.items()}


def summarize(bare: dict[str, list[dict]], consult: dict[str, list[dict]]) -> dict:
    tasks = sorted(consult)
    bare, consult, judge_excluded = align({t: bare.get(t, []) for t in tasks}, consult)
    rows = []
    for task in tasks:
        b, c = bare.get(task, []), consult.get(task, [])
        row = {
            "task": task,
            "bare": mean_reward(b, "reward"),
            "consult": mean_reward(c, "reward"),
            "floor_rate": {"bare": floor_rate(b), "consult": floor_rate(c)},
            "low_tail": {"bare": low_tail(b), "consult": low_tail(c)},
            "dimensions": {
                d: {"bare": mean_reward(b, d), "consult": mean_reward(c, d)}
                for d in DIMENSIONS
                if any(d in e["rewards"] for e in b + c)
            },
            "readouts": {r: {"bare": mean_reward(b, r), "consult": mean_reward(c, r)} for r in READOUTS},
            "failed": failed_trials(b + c),
        }
        row["lift"] = row["consult"] - row["bare"]
        rows.append(row)
    suite = compare(bare, consult)
    return {"tasks": rows, "suite_lift": suite["reward"], "suite": suite, "judge_excluded": judge_excluded,
            "rules": rule_scorecard(bare, consult),
            "skills": [skill_row(t, bare.get(t, []), consult.get(t, [])) for t in tasks]}


def failed_trials(entries: Iterable[dict]) -> list[str]:
    """Trials with an agent or verifier failure, or no reward; a missing reward counts as 0."""
    return [e["trial"] for e in entries if e.get("error") or e["reward"] is None]


def rule_pass_rates(by_task: dict[str, list[dict]]) -> dict[str, tuple[float, set[str]]]:
    """rule id -> (mean score over every trial that scored it, tasks that scored it)."""
    scores: dict[str, list[float]] = defaultdict(list)
    tasks: dict[str, set[str]] = defaultdict(set)
    for task, entries in by_task.items():
        record_task_rules(task, entries, scores, tasks)
    return {rule: (statistics.fmean(values), tasks[rule]) for rule, values in scores.items()}


def record_task_rules(task: str, entries: list[dict], scores: dict, tasks: dict) -> None:
    for rule, value in chain.from_iterable(e["rules"].items() for e in entries):
        scores[rule].append(value)
        tasks[rule].add(task)


def rule_scorecard(bare: dict[str, list[dict]], consult: dict[str, list[dict]]) -> list[dict]:
    """Per-rule pass rates; an arm with no trial that scored the rule shows None, not 0."""
    b, c = rule_pass_rates(bare), rule_pass_rates(consult)
    rows = []
    for rule in sorted(set(b) | set(c)):
        bare_rate, consult_rate = b.get(rule, (None, set()))[0], c.get(rule, (None, set()))[0]
        tasks = b.get(rule, (None, set()))[1] | c.get(rule, (None, set()))[1]
        lift = None if bare_rate is None or consult_rate is None else consult_rate - bare_rate
        rows.append({"rule": rule, "tasks": len(tasks), "bare": bare_rate, "consult": consult_rate, "lift": lift})
    return rows


def skill_row(task: str, bare: list[dict], consult: list[dict]) -> dict:
    """Consult-arm skills against the task's expected and silent lists; sign-off mode per arm."""
    meta = task_meta(task)
    read = Counter(chain.from_iterable(set(e["skills_read"]) for e in consult))
    trials = max(len(consult), 1)
    intended, silent = meta.get("intended_skills") or [], meta.get("expect_silent") or []
    return {
        "task": task,
        "fired": {s: read[s] / trials for s in intended if read[s]},
        "missed": [s for s in intended if not read[s]],
        "silent_violations": {s: read[s] / trials for s in silent if read[s]},
        "signoff_mode": {"bare": mode_counts(bare), "consult": mode_counts(consult)},
    }


def mode_counts(entries: list[dict]) -> dict[str, int]:
    return dict(Counter(e["signoff_mode"] for e in entries if e.get("signoff_mode")))


def render_markdown(summary: dict, bare_dir: Path, consult_dir: Path) -> str:
    lines = [
        f"# Lift: {consult_dir.name} vs {bare_dir.name}",
        "",
        "| task | bare | consult | lift | floor rate (bare / consult) | p25 (bare / consult) "
        "| skill_triggering (consult) | non_interruption (bare / consult) |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in summary["tasks"]:
        r, f, t = row["readouts"], row["floor_rate"], row["low_tail"]
        lines.append(
            f"| {row['task']} | {row['bare']:.3f} | {row['consult']:.3f} | {row['lift']:+.3f} "
            f"| {f['bare']:.0%} / {f['consult']:.0%} | {t['bare']:.2f} / {t['consult']:.2f} "
            f"| {r['skill_triggering']['consult']:.2f} "
            f"| {r['non_interruption']['bare']:.2f} / {r['non_interruption']['consult']:.2f} |"
        )
    lines += ["", *render_comparison(summary["suite"], "Suite lift"), ""]
    if summary["judge_excluded"]:
        lines += [JUDGE_EXCLUDED_NOTE, ""]
    for row in summary["tasks"]:
        if row["dimensions"]:
            dims = ", ".join(
                f"{d} {v['bare']:.2f}->{v['consult']:.2f}" for d, v in row["dimensions"].items()
            )
            lines.append(f"- {row['task']}: {dims}")
        if row["failed"]:
            lines.append(f"- {row['task']}: no reward for {', '.join(row['failed'])}")
    return "\n".join(lines + render_rules(summary["rules"]) + render_skills(summary["skills"])) + "\n"


def render_comparison(result: dict, label: str, before: str = "the earlier job") -> list[str]:
    lines = [
        f"{label}: {result['reward']:+.3f} ({interval_text(result['reward_interval'], '+.3f')})",
        f"Floor rate change: {result['floor_rate']:+.0%} ({interval_text(result['floor_rate_interval'], '+.0%')}). "
        f"Below the floor means verification failed or reward < {FLOOR_REWARD}.",
    ]
    if result["missing"]:
        lines.append(f"Left out, no trials in {before}: {', '.join(result['missing'])}")
    return lines


def interval_text(bounds: tuple[float, float] | None, spec: str) -> str:
    if bounds is None:
        return "no interval: needs 2+ trials per task in each job and some spread"
    lo, hi = bounds
    return f"90% interval {format(lo, spec)} to {format(hi, spec)}, {noise_verdict(lo, hi)}"


def noise_verdict(lo: float, hi: float) -> str:
    return "not distinguishable from noise" if lo <= 0.0 <= hi else "interval excludes 0"


def render_regression(result: dict, baseline_dir: Path) -> list[str]:
    return ["", f"## Against the earlier Consult job {baseline_dir.name}", "",
            *render_comparison(result, "Reward change")]


def aligned_comparison(before: dict[str, list[dict]], after: dict[str, list[dict]]) -> dict:
    """compare() after judge alignment, plus each compared task's mean reward in both jobs."""
    before, after, judge_excluded = align(before, after)
    result = compare(before, after)
    rows = [{"task": t, "before": mean_reward(before[t], "reward"), "after": mean_reward(after[t], "reward")}
            for t in result["tasks"]]
    failed = failed_trials(chain.from_iterable(before[t] + after[t] for t in result["tasks"]))
    return {**result, "judge_excluded": judge_excluded, "rows": rows, "failed": failed}


def stub_comparisons(bare: dict[str, list[dict]], stub: dict[str, list[dict]], consult: dict[str, list[dict]]) -> dict:
    """content: stub to consult, the effect of skill bodies. listing: bare to stub, the effect of listing and hook."""
    return {"content": aligned_comparison(stub, consult), "listing": aligned_comparison(bare, stub)}


def content_verdict(result: dict) -> str:
    if result["failed"]:
        return ("Verdict: withheld, failed trials are listed above. "
                "Rerun them before reading the change as a skill-content effect.")
    if result["reward_interval"] is None:
        return "Verdict: no interval, so this run cannot say whether skill content changes the reward."
    lo, hi = result["reward_interval"]
    if lo > 0.0:
        return "Verdict: consult beats stub, interval excludes 0. Skill content raises the reward."
    if hi < 0.0:
        return "Verdict: consult scores below stub, interval excludes 0. Skill content lowers the reward."
    return "Verdict: consult does not beat stub beyond noise, interval contains 0."


def render_stub(comparisons: dict) -> list[str]:
    content, listing = comparisons["content"], comparisons["listing"]
    return [*arm_section("Skill content: consult vs stub", content, "stub", "consult"), content_verdict(content),
            *arm_section("Listing and hook: stub vs bare", listing, "bare", "stub")]


def arm_section(title: str, result: dict, before: str, after: str) -> list[str]:
    lines = ["", f"## {title}", "", f"| task | {before} | {after} | {after} - {before} |", "| --- | ---: | ---: | ---: |"]
    lines += [f"| {r['task']} | {r['before']:.3f} | {r['after']:.3f} | {r['after'] - r['before']:+.3f} |"
              for r in result["rows"]]
    lines += ["", *render_comparison(result, "Reward change", f"the {before} job")]
    if result["failed"]:
        lines.append(f"Failed trials (no reward counts as 0): {', '.join(result['failed'])}")
    return lines + ([JUDGE_EXCLUDED_NOTE] if result["judge_excluded"] else [])


def render_rules(rows: list[dict]) -> list[str]:
    if not rows:
        return []
    lines = ["", "## Rules", "", "| rule | tasks | bare pass | consult pass | lift |", "| --- | ---: | ---: | ---: | ---: |"]
    lines += [
        f"| {r['rule']} | {r['tasks']} | {rate(r['bare'], '.2f')} | {rate(r['consult'], '.2f')} | {rate(r['lift'], '+.2f')} |"
        for r in rows
    ]
    return lines


def rate(value: float | None, spec: str) -> str:
    return "-" if value is None else format(value, spec)


def render_skills(rows: list[dict]) -> list[str]:
    lines = ["", "## Skills (consult arm)", "",
             "| task | fired | missed | silent violations | signoff_mode (bare / consult) |", "| --- | --- | --- | --- | --- |"]
    for r in rows:
        modes = f"{format_modes(r['signoff_mode']['bare'])} / {format_modes(r['signoff_mode']['consult'])}"
        lines.append(
            f"| {r['task']} | {format_shares(r['fired'])} | {', '.join(r['missed']) or 'none'} "
            f"| {format_shares(r['silent_violations'])} | {modes} |"
        )
    return lines


def format_shares(shares: dict[str, float]) -> str:
    return ", ".join(f"{skill} {share:.0%}" for skill, share in shares.items()) or "none"


def format_modes(counts: dict[str, int]) -> str:
    return ", ".join(f"{mode} {n}" for mode, n in counts.items()) or "-"


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("bare_job", type=Path)
    parser.add_argument("consult_job", type=Path)
    parser.add_argument("--baseline-consult", type=Path, help="an earlier Consult job to compare this one against")
    parser.add_argument("--stub", type=Path, help="a stub-arm job: adds consult vs stub and stub vs bare")
    args = parser.parse_args(argv[1:])
    bare_dir, consult_dir = args.bare_job, args.consult_job
    bare, consult = load_trials(bare_dir), load_trials(consult_dir)
    summary = summarize(bare, consult)
    markdown = render_markdown(summary, bare_dir, consult_dir)
    if args.stub:
        summary["stub"] = stub_comparisons(bare, load_trials(args.stub), consult)
        markdown += "\n".join(render_stub(summary["stub"])) + "\n"
    if args.baseline_consult:
        before, after, _ = align(load_trials(args.baseline_consult), consult)
        summary["regression"] = compare(before, after)
        markdown += "\n".join(render_regression(summary["regression"], args.baseline_consult)) + "\n"
    out_dir = consult_dir.parent / "lift"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / f"{consult_dir.name}.json").write_text(json.dumps(summary, indent=2))
    (out_dir / f"{consult_dir.name}.md").write_text(markdown)
    print(markdown)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
