#!/usr/bin/env python3
"""Count how often trials opened each skill reference file.

  uv run scripts/reference_reads.py runs/<job> [runs/<job> ...]

Prints a Markdown table: one row per reference file under
agents/.agents/skills/*/references/, plus any other reference path a trial
opened, and one column per job with the share of its trials that opened the
file. A reference nobody opens costs nothing at run time but still needs
upkeep; one opened in most trials may belong in its SKILL.md. The reference
audit reads this table.

A trial opened a reference when a tool call's arguments name
skills/<skill>/references/<file>: Claude Code's Read path or the text of a
Codex shell command. Tool results are not read, so a listing or grep output
that shows the path is not an open, and a call that failed is not one either.
Each trial counts a file once across all its step trajectories.

A shell command that reaches a reference by a relative path, after a cd or
through a workdir argument, is missed. Check one real trajectory from the host
before reading a 0 as a file nobody opened. Standard library only, so the
tests run in CI.
"""

from __future__ import annotations

import json
import re
import sys
from collections import Counter
from itertools import chain
from pathlib import Path

EVAL_DIR = Path(__file__).resolve().parent.parent
SKILLS_DIR = EVAL_DIR.parent / "agents" / ".agents" / "skills"
sys.path.insert(0, str(EVAL_DIR / "verifier" / "shared"))
import consult_lib as cl  # noqa: E402

REFERENCE_SUFFIXES = (".md", ".yaml", ".yml")
REFERENCE_PATH_RE = re.compile(
    r"skills/([a-z][a-z0-9-]*/references/[\w./-]+\.(?:" + "|".join(s[1:] for s in REFERENCE_SUFFIXES) + "))")


def trial_references(trial_dir: Path) -> set[str]:
    """skill/references/file paths any of the trial's trajectories opened without error."""
    paths = [trial_dir / "agent" / "trajectory.json", *sorted(trial_dir.glob("steps/*/agent/trajectory.json"))]
    calls = chain.from_iterable(cl.load_trajectory(p).calls for p in paths)
    opened = (REFERENCE_PATH_RE.findall(json.dumps(c.arguments)) for c in calls if not call_failed(c))
    return set(chain.from_iterable(opened))


def call_failed(call: cl.ToolCall) -> bool:
    """A tool call the host marked as an error, or a shell command that exited non-zero."""
    return any(extra.get("tool_result_is_error") for extra in call.result_extras) or cl.command_failed(call)


def job_reads(job_dir: Path) -> tuple[Counter, int]:
    """(trials that opened each reference, trial count) for one Harbor job dir."""
    trials = [p.parent for p in sorted(job_dir.glob("*/result.json"))]
    return Counter(chain.from_iterable(trial_references(t) for t in trials)), len(trials)


def canonical_references() -> list[str]:
    files = (p for p in SKILLS_DIR.glob("*/references/**/*") if p.is_file() and p.suffix in REFERENCE_SUFFIXES)
    return sorted(p.relative_to(SKILLS_DIR).as_posix() for p in files)


def render(jobs: dict[str, tuple[Counter, int]]) -> str:
    opened = set(chain.from_iterable(counts for counts, _ in jobs.values()))
    rows = sorted(set(canonical_references()) | opened)
    lines = [f"| reference | {' | '.join(jobs)} |", "| --- |" + " ---: |" * len(jobs)]
    for ref in rows:
        cells = " | ".join(f"{counts[ref]}/{trials}" for counts, trials in jobs.values())
        lines.append(f"| {ref} | {cells} |")
    return "\n".join(lines) + "\n"


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__, file=sys.stderr)
        return 2
    missing = [arg for arg in argv[1:] if not Path(arg).is_dir()]
    if missing:
        print(f"no job dir: {', '.join(missing)}", file=sys.stderr)
        return 2
    jobs = {Path(arg).name: job_reads(Path(arg)) for arg in argv[1:]}
    print(render(jobs), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
