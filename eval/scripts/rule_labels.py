#!/usr/bin/env python3
"""Hand-label rule checks so the rules dimension can be calibrated.

  uv run scripts/rule_labels.py export <sheet.csv> runs/<job> [runs/<job> ...]
  uv run scripts/rule_labels.py agree <sheet.csv>

The rules dimension weighs 0 in reward.<kind>.toml until its heuristic checks
agree with a person. export writes one CSV row per rule verdict in each trial
of the given jobs, read the way lift.py reads them (a sign-off rule counts only
when the build step's verification passed). Each row carries the job, trial,
task, rule id, the rule's text from its SKILL.md, the automated score, and the
trial dir that holds the evidence (judge-bundle.md, trajectory.json). The
proposed, human, and note columns start empty: a draft label can go in
proposed, and the reviewer writes pass or fail in human.

agree prints, per rule, how many labelled rows the automated check matched. A
score of 0.5 or more counts as a pass. The weight decision reads that table.
Standard library only, so the tests run in CI.
"""

from __future__ import annotations

import csv
import re
import sys
from collections import defaultdict
from pathlib import Path

EVAL_DIR = Path(__file__).resolve().parent.parent
SKILLS_DIR = EVAL_DIR.parent / "agents" / ".agents" / "skills"
sys.path.insert(0, str(EVAL_DIR / "scripts"))
import lift  # noqa: E402

COLUMNS = ("job", "trial", "task", "rule", "rule_text", "automated", "trial_dir", "proposed", "human", "note")
LABELS = ("pass", "fail")
RULE_ITEM_RE = re.compile(r"^(\d+)\.\s", re.MULTILINE)


def export_rows(job_dir: Path) -> list[dict]:
    """One row per rule verdict in each trial of the job, sorted by trial then rule."""
    trials = sorted(((task, e) for task, entries in lift.load_trials(job_dir).items() for e in entries),
                    key=lambda pair: pair[1]["trial"])
    return [verdict_row(job_dir, task, entry, rule, score)
            for task, entry in trials for rule, score in sorted(entry["rules"].items())]


def verdict_row(job_dir: Path, task: str, entry: dict, rule: str, score: float) -> dict:
    return {"job": job_dir.name, "trial": entry["trial"], "task": task.split("/")[-1], "rule": rule,
            "rule_text": rule_text(rule), "automated": score, "trial_dir": str(job_dir / entry["trial"]),
            "proposed": "", "human": "", "note": ""}


def rule_text(rule_id: str) -> str:
    """The numbered rule's text from its skill's ## Rules section, tables dropped; empty when not found."""
    skill, number = rule_id.rsplit(".", 1)
    path = SKILLS_DIR / skill / "SKILL.md"
    if not path.is_file():
        return ""
    _, found, rest = path.read_text().partition("\n## Rules\n")
    section = rest.split("\n## ", 1)[0].split("\n### ", 1)[0]
    parts = RULE_ITEM_RE.split(section)
    items = dict(zip(parts[1::2], parts[2::2]))
    lines = [line.strip() for line in items.get(number, "").splitlines() if line.strip()]
    return " ".join(line for line in lines if not line.startswith("|")).replace("**", "") if found else ""


def write_sheet(path: Path, rows: list[dict]) -> None:
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def read_sheet(path: Path) -> list[dict]:
    """The sheet's rows; SystemExit when a human label is neither empty, pass, nor fail."""
    with path.open(newline="") as handle:
        rows = list(csv.DictReader(handle))
    bad = [r for r in rows if r["human"].strip() not in ("", *LABELS)]
    if bad:
        raise SystemExit(f"human must be pass or fail; got {bad[0]['human']!r} for {bad[0]['rule']}")
    return rows


def agreement(rows: list[dict]) -> dict[str, tuple[int, int]]:
    """rule -> (rows where the check matched the human label, labelled rows)."""
    counts: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    for row in rows:
        label = row["human"].strip()
        if not label:
            continue
        counts[row["rule"]][0] += (float(row["automated"]) >= 0.5) == (label == "pass")
        counts[row["rule"]][1] += 1
    return {rule: (matched, labelled) for rule, (matched, labelled) in sorted(counts.items())}


def render_agreement(result: dict[str, tuple[int, int]]) -> str:
    lines = ["| rule | labelled | agree | agreement |", "| --- | ---: | ---: | ---: |"]
    lines += [f"| {rule} | {n} | {m} | {m / n:.0%} |" for rule, (m, n) in result.items()]
    return "\n".join(lines) + "\n"


def main(argv: list[str]) -> int:
    if len(argv) >= 4 and argv[1] == "export":
        rows = [row for job in argv[3:] for row in export_rows(Path(job))]
        write_sheet(Path(argv[2]), rows)
        print(f"wrote {len(rows)} rule verdicts to {argv[2]}")
        return 0
    if len(argv) == 3 and argv[1] == "agree":
        print(render_agreement(agreement(read_sheet(Path(argv[2])))), end="")
        return 0
    print(__doc__, file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
