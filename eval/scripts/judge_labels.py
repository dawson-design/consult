#!/usr/bin/env python3
"""Hand-label rubric judge answers so each rubric dimension can be calibrated.

  uv run scripts/judge_labels.py export <sheet.csv> runs/<job>-rejudged [...] [--per-dimension 50] [--seed 1]
  uv run scripts/judge_labels.py serve <sheet.csv> [--port 8765] [--no-browser]
  uv run scripts/judge_labels.py agree <sheet.csv>
  uv run scripts/judge_labels.py repeat runs/<job>-rejudged runs/<job>-rejudged-repeat [<first> <second> ...]

A rubric dimension can carry a claim on the site only when its judge agrees
with the maintainer. export samples judge answers from rejudged jobs (written
by rescore.py --rejudge): per dimension, half from bare trials and half from
consult trials, spread across tasks by a seeded shuffle. Each job's name must
say its arm (-bare or -consult).

The labeller works blind. The sheet shows each item (question, what to look
at, when yes, when no) and an opaque case id, but not the judge's answer, its
reason, its evidence (whose form differs by answer: a quote for yes or no, the
files checked for a missing thing, what it could not find for unknown), or the
arm. Each case's material is
in <sheet>-cases/<case>.md: the task instruction, the agent's earlier replies
the judges read, and the judge bundle (the diff and the final message), with
Consult's names scrubbed as the judges' view scrubs them. The labeller may
still recognise an arm from its style. The answers, reasons, evidence, and arms
go to <sheet>.key.json, which agree reads. export refuses to overwrite any of these,
so a rerun cannot erase labels.

serve opens a local page (scripts/label_page.py) that shows each item beside
its case and saves each answer into the sheet; the sheet can also be edited
in a spreadsheet. The labeller writes yes or no in the human column: whether the item holds for
the code, with yes meaning the requirement is met, as the judge answers.

agree prints, per dimension:
  kappa    Cohen's kappa between judge and human over rows both answered yes or no
  bias     per arm, the judge's yes-rate minus the human's on those rows
  unknown  the judge's unknown rate over every answer in the exported jobs
and whether the dimension passes the calibration gate: kappa at least 0.7,
each arm's bias under 0.1 in size, and unknown under 10%.

repeat compares two rejudge passes over the same trials, item by item, and
prints per dimension how often the answers match; the gate needs 0.9.
Standard library only, so the tests run in CI.
"""

from __future__ import annotations

import argparse
import csv
import json
import random
import re
import sys
from collections import defaultdict
from pathlib import Path

EVAL_DIR = Path(__file__).resolve().parent.parent
TASKS_DIR = EVAL_DIR / "tasks"
sys.path.insert(0, str(EVAL_DIR / "scripts"))
sys.path.insert(0, str(EVAL_DIR / "verifier" / "shared"))
import consult_lib as cl
import judge_runner as jr
from rule_labels import evidence_dir

COLUMNS = (
    "row",
    "case",
    "task",
    "dimension",
    "item",
    "tier",
    "question",
    "look_at",
    "yes_when",
    "no_when",
    "human",
    "note",
)
LABELS = ("yes", "no")
ARM_RE = re.compile(r"-(bare|consult)(?=-|$)")
KAPPA_MIN = 0.7
BIAS_MAX = 0.1
UNKNOWN_MAX = 0.1
REPEAT_MIN = 0.9


# ------------------------------------------------------------------- answers


def job_arm(job_dir: Path) -> str:
    """bare or consult, from the job's name; SystemExit when the name says neither."""
    match = ARM_RE.search(job_dir.name)
    if not match:
        raise SystemExit(f"{job_dir.name}: the job name must say its arm (-bare or -consult)")
    return match.group(1)


def judged_trials(job_dir: Path) -> list[dict]:
    """Each trial in the job whose rubric judges ran and rescore did not flag: its task, final-step dir, and answers."""
    trials = []
    for result_path in sorted(job_dir.glob("*/result.json")):
        trial_dir = result_path.parent
        final = evidence_dir(trial_dir)
        answers_path = final / "verifier" / "judge-items.json"
        result = json.loads(result_path.read_text())
        # rescore.py flagged it, such as a workspace that is not the one judged: its answers do not count.
        if not answers_path.is_file() or (result.get("rescore") or {}).get("flags"):
            continue
        task = (result.get("task_name") or trial_dir.name.split("__")[0]).split("/")[-1]
        items = json.loads(answers_path.read_text())["items"]
        trials.append({"job": job_dir.name, "trial": trial_dir.name, "task": task, "final": final, "items": items})
    return trials


def all_answers(trials: list[dict], arm: str) -> list[dict]:
    """One record per rubric item, including those a failed call left unknown (source missing or invalid)."""
    return [
        {"job": t["job"], "trial": t["trial"], "task": t["task"], "arm": arm, "final": t["final"], **item}
        for t in trials
        for item in t["items"]
    ]


# ------------------------------------------------------------------- export


def sample(answers: list[dict], per_dimension: int, seed: int) -> list[dict]:
    """Up to per_dimension answers per dimension, half per arm, taken round-robin across tasks after a shuffle."""
    rng = random.Random(seed)
    picked = []
    for dimension in jr.DIMENSIONS:
        for arm in ("bare", "consult"):
            pool = [a for a in answers if a["dimension"] == dimension and a["arm"] == arm]
            rng.shuffle(pool)
            picked += round_robin(pool, per_dimension // 2)
    rng.shuffle(picked)
    return picked


def round_robin(pool: list[dict], count: int) -> list[dict]:
    """count answers, cycling through the tasks in the pool's order so no task dominates."""
    by_task: dict[str, list[dict]] = defaultdict(list)
    for answer in pool:
        by_task[answer["task"]].append(answer)
    queues, taken = list(by_task.values()), []
    while len(taken) < count and any(queues):
        for queue in queues:
            if queue and len(taken) < count:
                taken.append(queue.pop(0))
    return taken


def item_definitions(task: str) -> dict[str, dict]:
    """The task's resolved rubric items by id, as the judges read them."""
    path = TASKS_DIR / task / "tests" / "rubric" / "items.json"
    return {item["id"]: item for item in json.loads(path.read_text())["items"]}


def case_ids(picked: list[dict]) -> dict[tuple[str, str], str]:
    """An opaque id per trial, numbered in the sampled order, so it says nothing about the arm."""
    ids: dict[tuple[str, str], str] = {}
    for answer in picked:
        ids.setdefault((answer["job"], answer["trial"]), f"c{len(ids) + 1:03d}")
    return ids


def sheet_row(number: int, case: str, answer: dict) -> dict:
    item = item_definitions(answer["task"])[answer["id"]]
    return {
        "row": f"r{number:03d}",
        "case": case,
        "task": answer["task"],
        "dimension": answer["dimension"],
        "item": answer["id"],
        "tier": answer["tier"],
        **{key: jr.scrub(item[key]) for key in ("question", "look_at", "yes_when", "no_when")},
        "human": "",
        "note": "",
    }


def case_text(case: str, answer: dict) -> str:
    """The material a labeller reads for one case, scrubbed as the judges' view is."""
    instruction = (TASKS_DIR / answer["task"] / "tests" / "rubric" / "instruction.md").read_text()
    steps = cl.load_trajectory(answer["final"] / "agent" / "trajectory.json").steps
    replies = jr.earlier_replies(instruction, steps)
    bundle = (answer["final"] / "verifier" / "judge-bundle.md").read_text()
    sections = [f"# Case {case}: {answer['task']}", "", "## Request", "", instruction.strip(), ""]
    for heading, reply in replies:
        sections += [f"## {heading}", "", reply.strip() or "(none)", ""]
    sections += ["## The change and the final message", "", bundle.strip(), ""]
    return jr.scrub("\n".join(sections))


def unknown_totals(answers: list[dict]) -> dict[str, dict[str, int]]:
    """dimension -> items and unknowns over every item, failed calls included: all score as unknown."""
    totals: dict[str, dict[str, int]] = defaultdict(lambda: {"answers": 0, "unknown": 0})
    for answer in answers:
        totals[answer["dimension"]]["answers"] += 1
        totals[answer["dimension"]]["unknown"] += answer["answer"] == "unknown"
    return dict(totals)


def key_path(sheet: Path) -> Path:
    return sheet.with_name(f"{sheet.stem}.key.json")


def cases_dir(sheet: Path) -> Path:
    return sheet.with_name(f"{sheet.stem}-cases")


def export(sheet: Path, jobs: list[Path], per_dimension: int, seed: int) -> int:
    existing = [str(p) for p in (sheet, key_path(sheet), cases_dir(sheet)) if p.exists()]
    if existing:
        print(f"{', '.join(existing)} exists and may hold labels; export to a new sheet", file=sys.stderr)
        return 2
    everything = [a for job in jobs for a in all_answers(judged_trials(job), job_arm(job))]
    # Only the judge's own answers are labelled; a failed call has nothing to agree with.
    answers = [a for a in everything if a.get("source") == "judge"]
    if not answers:
        print("no judge answers in the given jobs; rejudge them with rescore.py --rejudge", file=sys.stderr)
        return 2
    picked = sample(answers, per_dimension, seed)
    ids = case_ids(picked)
    rows = [sheet_row(n, ids[(a["job"], a["trial"])], a) for n, a in enumerate(picked, start=1)]
    cases_dir(sheet).mkdir(parents=True)
    for case, answer in {ids[(a["job"], a["trial"])]: a for a in picked}.items():
        (cases_dir(sheet) / f"{case}.md").write_text(case_text(case, answer))
    key = {
        "rows": {
            row["row"]: {k: a[k] for k in ("job", "trial", "arm", "answer", "evidence", "why")}
            for row, a in zip(rows, picked, strict=True)
        },
        "totals": unknown_totals(everything),
        "seed": seed,
    }
    with sheet.open("x", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    key_path(sheet).write_text(json.dumps(key, indent=2) + "\n")
    print(f"wrote {len(rows)} items from {len(ids)} cases to {sheet}")
    return 0


# ------------------------------------------------------------------- agree


def read_labels(sheet: Path) -> list[dict]:
    """Each sheet row joined to its key entry; SystemExit naming a row with an unreadable label."""
    key = json.loads(key_path(sheet).read_text())["rows"]
    # utf-8-sig: a spreadsheet's "CSV UTF-8" save starts the file with a byte-order mark.
    with sheet.open(newline="", encoding="utf-8-sig") as handle:
        rows = list(csv.DictReader(handle))
    joined = []
    for row in rows:
        label = (row.get("human") or "").strip().lower()
        if label not in ("", *LABELS):
            raise SystemExit(f"{row['row']} ({row['item']}): human must be yes or no, got {row['human']!r}")
        if row["row"] not in key:
            raise SystemExit(f"{row['row']} is not in {key_path(sheet).name}: the sheet and key do not match")
        joined.append({**row, **key[row["row"]], "human": label})
    return joined


def kappa(pairs: list[tuple[str, str]]) -> float | None:
    """Cohen's kappa for two raters' yes/no answers; None when chance agreement is total."""
    if not pairs:
        return None
    n = len(pairs)
    observed = sum(a == b for a, b in pairs) / n
    first_yes = sum(a == "yes" for a, _ in pairs) / n
    second_yes = sum(b == "yes" for _, b in pairs) / n
    chance = first_yes * second_yes + (1 - first_yes) * (1 - second_yes)
    return None if chance == 1 else (observed - chance) / (1 - chance)


def yes_rate(answers: list[str]) -> float | None:
    return sum(a == "yes" for a in answers) / len(answers) if answers else None


def dimension_agreement(rows: list[dict], totals: dict) -> dict:
    """The gate's numbers for one dimension's labelled rows."""
    both = [r for r in rows if r["human"] and r["answer"] in jr.MET]
    bias = {}
    for arm in ("bare", "consult"):
        arm_rows = [r for r in both if r["arm"] == arm]
        judge, human = yes_rate([r["answer"] for r in arm_rows]), yes_rate([r["human"] for r in arm_rows])
        bias[arm] = None if judge is None else judge - human
    unknown = totals["unknown"] / totals["answers"] if totals.get("answers") else None
    k = kappa([(r["answer"], r["human"]) for r in both])
    passes = (
        k is not None
        and k >= KAPPA_MIN
        and all(b is not None and abs(b) < BIAS_MAX for b in bias.values())
        and unknown is not None
        and unknown < UNKNOWN_MAX
    )
    labelled = sum(1 for r in rows if r["human"])
    return {"labelled": labelled, "compared": len(both), "kappa": k, "bias": bias, "unknown": unknown, "passes": passes}


def agreement(sheet: Path) -> dict[str, dict]:
    rows = read_labels(sheet)
    totals = json.loads(key_path(sheet).read_text())["totals"]
    return {
        d: dimension_agreement([r for r in rows if r["dimension"] == d], totals.get(d, {}))
        for d in jr.DIMENSIONS
        if any(r["dimension"] == d for r in rows)
    }


def number(value: float | None, fmt: str) -> str:
    return "-" if value is None else format(value, fmt)


def render_agreement(result: dict[str, dict]) -> str:
    lines = [
        "| dimension | labelled | compared | kappa | bias bare | bias consult | unknown | gate |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for dimension, r in result.items():
        lines.append(
            f"| {dimension} | {r['labelled']} | {r['compared']} | {number(r['kappa'], '.2f')} "
            f"| {number(r['bias']['bare'], '+.2f')} | {number(r['bias']['consult'], '+.2f')} "
            f"| {number(r['unknown'], '.0%')} | {'pass' if r['passes'] else 'fail'} |"
        )
    lines += [
        "",
        (
            f"Gate: kappa >= {KAPPA_MIN}, each arm's |bias| < {BIAS_MAX}, unknown < {UNKNOWN_MAX:.0%}; "
            f"repeat agreement >= {REPEAT_MIN} comes from the repeat command."
        ),
    ]
    return "\n".join(lines) + "\n"


# ------------------------------------------------------------------- repeat


def answers_by_key(job_dir: Path) -> dict[tuple[str, str], dict]:
    """(trial, item id) -> the judge's answer record, for every judged trial in a rejudged job."""
    return {(t["trial"], item["id"]): item for t in judged_trials(job_dir) for item in t["items"]}


def repeat_agreement(pairs: list[tuple[Path, Path]]) -> dict[str, dict[str, int]]:
    """dimension -> items in both passes, and how many got the same answer."""
    counts: dict[str, dict[str, int]] = defaultdict(lambda: {"compared": 0, "same": 0})
    for first, second in pairs:
        a, b = answers_by_key(first), answers_by_key(second)
        for key in sorted(a.keys() & b.keys()):
            if a[key].get("source") != "judge" or b[key].get("source") != "judge":
                continue
            tally = counts[a[key]["dimension"]]
            tally["compared"] += 1
            tally["same"] += a[key]["answer"] == b[key]["answer"]
    return {d: counts[d] for d in jr.DIMENSIONS if d in counts}


def render_repeat(result: dict[str, dict[str, int]]) -> str:
    lines = ["| dimension | compared | same | agreement | gate |", "| --- | ---: | ---: | ---: | --- |"]
    for dimension, t in result.items():
        rate = t["same"] / t["compared"] if t["compared"] else None
        gate = "pass" if rate is not None and rate >= REPEAT_MIN else "fail"
        lines.append(f"| {dimension} | {t['compared']} | {t['same']} | {number(rate, '.0%')} | {gate} |")
    return "\n".join(lines) + "\n"


# ------------------------------------------------------------------- main


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)
    exporter = commands.add_parser("export", help="sample judge answers into a blind label sheet")
    exporter.add_argument("sheet", type=Path)
    exporter.add_argument("jobs", nargs="+", type=Path)
    exporter.add_argument("--per-dimension", type=int, default=50)
    exporter.add_argument("--seed", type=int, default=1)
    server = commands.add_parser("serve", help="label the sheet in a local browser page")
    server.add_argument("sheet", type=Path)
    server.add_argument("--port", type=int, default=8765)
    server.add_argument("--no-browser", action="store_true", help="print the URL without opening it")
    commands.add_parser("agree", help="judge-human agreement per dimension").add_argument("sheet", type=Path)
    repeater = commands.add_parser("repeat", help="agreement between two rejudge passes")
    repeater.add_argument("dirs", nargs="+", type=Path, help="pairs: first pass, second pass")
    args = parser.parse_args(argv[1:])
    if args.command == "export":
        return export(args.sheet, args.jobs, args.per_dimension, args.seed)
    if args.command == "serve":
        import label_page

        return label_page.serve(args.sheet, cases_dir(args.sheet), args.port, not args.no_browser)
    if args.command == "agree":
        print(render_agreement(agreement(args.sheet)), end="")
        return 0
    if len(args.dirs) % 2:
        parser.error("repeat takes pairs of rejudged job dirs: first pass, then second pass")
    pairs = list(zip(args.dirs[::2], args.dirs[1::2], strict=True))
    print(render_repeat(repeat_agreement(pairs)), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
