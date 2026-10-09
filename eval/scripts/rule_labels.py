#!/usr/bin/env python3
"""Hand-label rule checks so the rules dimension can be calibrated.

  uv run scripts/rule_labels.py export <sheet.csv> runs/<job> [runs/<job> ...]
  uv run scripts/rule_labels.py agree <sheet.csv>

The rules dimension weighs 0 in reward.<kind>.toml until its heuristic checks
agree with a person. export writes one CSV row per rule verdict in each trial
of the given jobs, read the way lift.py reads them. Sign-off rules are left
out: they score in the brief step's suite, never in the rules dimension. Each
row carries the job, trial, task, rule id, the rule's text from its SKILL.md
as it reads at export time, the automated score, and evidence_dir, the dir
that holds the final step's agent/trajectory.json and verifier/judge-bundle.md.
The proposed, human, and note columns start empty: a draft label can go in
proposed, and the reviewer writes pass or fail in human. export refuses to
overwrite an existing sheet, so a rerun cannot erase labels.

agree prints, per rule, the labelled rows, how many the automated check
matched, and its false passes and false fails. A score of 0.5 or more counts as
a pass. The weight decision reads that table. Standard library only, so the
tests run in CI.
"""

from __future__ import annotations

import csv
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

EVAL_DIR = Path(__file__).resolve().parent.parent
SKILLS_DIR = EVAL_DIR.parent / "agents" / ".agents" / "skills"
sys.path.insert(0, str(EVAL_DIR / "scripts"))
import lift  # noqa: E402
import consult_rules as cr  # noqa: E402  (lift puts verifier/shared on the path)

COLUMNS = ("job", "trial", "task", "rule", "rule_text", "automated", "evidence_dir", "proposed", "human", "note")
LABELS = ("pass", "fail")
AGREEMENT_FIELDS = ("labelled", "agree", "false_pass", "false_fail")
RULE_ITEM_RE = re.compile(r"^(\d+)\.\s", re.MULTILINE)


def export_rows(job_dir: Path) -> list[dict]:
    """One row per scored rule verdict in each trial of the job, sorted by trial then rule."""
    trials = sorted(((task, e) for task, entries in lift.load_trials(job_dir).items() for e in entries),
                    key=lambda pair: pair[1]["trial"])
    return [verdict_row(job_dir, task, entry, rule)
            for task, entry in trials for rule in cr.scored_rule_ids(sorted(entry["rules"]))]


def verdict_row(job_dir: Path, task: str, entry: dict, rule: str) -> dict:
    return {"job": job_dir.name, "trial": entry["trial"], "task": task.split("/")[-1], "rule": rule,
            "rule_text": rule_text(rule), "automated": entry["rules"][rule],
            "evidence_dir": str(evidence_dir(job_dir.resolve() / entry["trial"])),
            "proposed": "", "human": "", "note": ""}


def evidence_dir(trial_dir: Path) -> Path:
    """The trial dir, or its last step's dir in a multi-step trial: where the final trajectory and bundle live."""
    result = json.loads((trial_dir / "result.json").read_text())
    steps = [s["step_name"] for s in result.get("step_results") or []]
    return trial_dir / "steps" / steps[-1] if steps else trial_dir


def rule_text(rule_id: str) -> str:
    """The numbered rule's text from its skill's ## Rules section, tables dropped; empty when not found."""
    skill, number = rule_id.rsplit(".", 1)
    path = SKILLS_DIR / skill / "SKILL.md"
    if not path.is_file():
        return ""
    _, found, rest = path.read_text().partition("\n## Rules\n")
    if not found:
        return ""
    section = rest.split("\n## ", 1)[0].split("\n### ", 1)[0]
    parts = RULE_ITEM_RE.split(section)
    items = dict(zip(parts[1::2], parts[2::2]))
    lines = [line.strip() for line in items.get(number, "").splitlines() if line.strip()]
    return " ".join(line for line in lines if not line.startswith("|")).replace("**", "")


def write_sheet(path: Path, rows: list[dict]) -> None:
    """Write a new sheet; FileExistsError when one is already there, since it may hold labels."""
    with path.open("x", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def read_sheet(path: Path) -> list[dict]:
    """The sheet's rows with labels lower-cased and scores as numbers; SystemExit naming a row that is unreadable."""
    with path.open(newline="") as handle:
        reader = csv.DictReader(handle)
        missing = [c for c in ("rule", "automated", "human") if c not in (reader.fieldnames or [])]
        if missing:
            raise SystemExit(f"{path} has no {', '.join(missing)} column; export a sheet with rule_labels.py")
        return [parse_row(number, row) for number, row in enumerate(reader, start=2)]


def parse_row(number: int, row: dict) -> dict:
    where = f"row {number} ({row.get('trial') or '?'}, {row.get('rule') or '?'})"
    label = (row.get("human") or "").strip().lower()
    if label not in ("", *LABELS):
        raise SystemExit(f"{where}: human must be pass or fail, got {row['human']!r}")
    try:
        score = float(row.get("automated") or "")
    except ValueError:
        raise SystemExit(f"{where}: automated must be a number, got {row.get('automated')!r}") from None
    return {**row, "human": label, "automated": score}


def agreement(rows: list[dict]) -> dict[str, dict[str, int]]:
    """rule -> labelled rows, rows the check agreed on, false passes (check passed, human failed), false fails."""
    counts: dict[str, dict[str, int]] = defaultdict(lambda: dict.fromkeys(AGREEMENT_FIELDS, 0))
    for row in rows:
        if not row["human"]:
            continue
        check_pass, human_pass = row["automated"] >= 0.5, row["human"] == "pass"
        tally = counts[row["rule"]]
        tally["labelled"] += 1
        tally["agree"] += check_pass == human_pass
        tally["false_pass"] += check_pass and not human_pass
        tally["false_fail"] += human_pass and not check_pass
    return dict(sorted(counts.items()))


def render_agreement(result: dict[str, dict[str, int]]) -> str:
    lines = ["| rule | labelled | agree | false pass | false fail | agreement |", "| --- | ---: | ---: | ---: | ---: | ---: |"]
    lines += [f"| {rule} | {t['labelled']} | {t['agree']} | {t['false_pass']} | {t['false_fail']} "
              f"| {t['agree'] / t['labelled']:.0%} |" for rule, t in result.items()]
    return "\n".join(lines) + "\n"


def export(sheet: Path, jobs: list[Path]) -> int:
    empty = [str(job) for job in jobs if not any(job.glob("*/result.json"))]
    if empty:
        print(f"no trials in {', '.join(empty)}", file=sys.stderr)
        return 2
    rows = [row for job in jobs for row in export_rows(job)]
    try:
        write_sheet(sheet, rows)
    except FileExistsError:
        print(f"{sheet} exists and may hold labels; export to a new file", file=sys.stderr)
        return 2
    print(f"wrote {len(rows)} rule verdicts to {sheet}")
    return 0


def main(argv: list[str]) -> int:
    if len(argv) >= 4 and argv[1] == "export":
        return export(Path(argv[2]), [Path(job) for job in argv[3:]])
    if len(argv) == 3 and argv[1] == "agree":
        print(render_agreement(agreement(read_sheet(Path(argv[2])))), end="")
        return 0
    print(__doc__, file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
