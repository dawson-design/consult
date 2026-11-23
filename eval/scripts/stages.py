"""Per-stage cost and resume additions of a multi-step trial, for the lift report's cost tables.

lift.py calls stage_costs() and resume_figures() on each trial's final-step trajectory. With resume_trajectory that
trajectory holds the whole session, one prompt per Harbor step, and each step's agent record holds the running total
of the session's cost and output tokens. activity.is_prompt says which user steps are prompts.

A resumed turn adds tokens to the context beyond the stop message and the prompt: Claude Code re-attaches snippets
of files that changed since the last turn. Every later call reads them again from the cache.

The resume cost uses per-token rates fitted to each call's cost_usd (token_rates). That per-call estimate prices
cache writes about $3 per million tokens below the step records the stage costs and trial totals come from, so the
resume cost runs a little low next to them: on the 11-22 staged-commissions jobs, by about $0.23 per trial for
Consult and $0.08 for bare.
"""

from __future__ import annotations

import sys
from collections.abc import Iterator
from itertools import pairwise
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "verifier" / "shared"))
import activity
import consult_lib as cl

STAGE_METRICS = ("api_calls", "cost_usd", "output_tokens")
# The usual rough ratio for English and code; prompts are short, so the estimate barely moves the result.
CHARS_PER_TOKEN = 4


def resumed_session(result: dict) -> bool:
    """Each step continues the last step's session (Harbor's resume_trajectory)."""
    return bool(((result.get("config") or {}).get("agent") or {}).get("resume_trajectory"))


def is_api_call(step: dict) -> bool:
    """An agent step with token metrics: one API call."""
    return step.get("source") == "agent" and "prompt_tokens" in (step.get("metrics") or {})


def is_main_call(step: dict) -> bool:
    """An API call in the main session, not a subagent's, which keeps its own context."""
    return is_api_call(step) and not (step.get("extra") or {}).get("is_sidechain")


def brief_count(result: dict) -> int | None:
    """How many of a trial's Harbor steps open a brief, read from its own step names (ending in `brief`). A
    single-step trial has one. None for a multi-step trial with no step so named."""
    steps = result.get("step_results") or []
    if not steps:
        return 1
    return sum(1 for step in steps if str(step.get("step_name", "")).endswith("brief")) or None


def stage_of(step_name: str) -> str:
    """The stage a Harbor step belongs to: `s2-approve` is in stage `s2`; a name without a dash is its own stage."""
    return step_name.split("-", 1)[0]


def stage_costs(result: dict, trajectory: cl.Trajectory) -> list[dict] | None:
    """Per stage, in order: API calls, cost, and output tokens.

    API calls come from splitting the trajectory at each prompt; cost and output tokens from the increase in the
    step records' running totals, so the stages sum to the trial's totals. None unless the trial is a resumed
    multi-step trial whose prompts match its steps one to one and whose records all carry both totals.
    """
    steps = result.get("step_results") or []
    if len(steps) < 2 or not resumed_session(result):
        return None
    calls = calls_per_prompt(trajectory)
    records = [s.get("agent_result") or {} for s in steps]
    costs = increments([r.get("cost_usd") for r in records])
    tokens = increments([r.get("n_output_tokens") for r in records])
    if len(calls) != len(steps) or costs is None or tokens is None:
        return None
    stages: dict[str, dict] = {}
    for step, figures in zip(steps, zip(calls, costs, tokens, strict=True), strict=True):
        row = stages.setdefault(stage_of(step["step_name"]), dict.fromkeys(STAGE_METRICS, 0))
        for metric, value in zip(STAGE_METRICS, figures, strict=True):
            row[metric] += value
    return [{"stage": name, **row} for name, row in stages.items()]


def calls_per_prompt(trajectory: cl.Trajectory) -> list[int]:
    """API calls after each prompt, up to the next. Calls before the first prompt get a count of their own, so the
    counts no longer match the steps."""
    counts: list[int] = []
    for step in trajectory.steps:
        if activity.is_prompt(step) or (not counts and is_api_call(step)):
            counts.append(0)
        if is_api_call(step):
            counts[-1] += 1
    return counts


def increments(totals: list[float | None]) -> list[float] | None:
    """Each running total's increase over the one before; None when any total is missing."""
    if any(t is None for t in totals):
        return None
    return [t - before for t, before in zip(totals, [0, *totals[:-1]], strict=True)]


def resume_figures(trajectory: cl.Trajectory) -> dict[str, float | None]:
    """Tokens the resumed turns added, and what they cost: written to the cache once, then read by every later call.

    Priced at the trial's own rates, fitted to its per-call cost estimates (token_rates). Both None without token
    metrics; the cost is None when the rates cannot be fitted and some turn added tokens.
    """
    if not any(map(is_main_call, trajectory.steps)):
        return {"resume_tokens": None, "resume_cost_usd": None}
    added = list(resume_additions(trajectory))
    tokens = sum(n for n, _ in added)
    if not tokens:
        return {"resume_tokens": 0, "resume_cost_usd": 0.0}
    rates = token_rates([s["metrics"] for s in trajectory.steps if is_api_call(s)])
    cost = None if rates is None else sum(n * (rates[0] + reads * rates[1]) for n, reads in added)
    return {"resume_tokens": tokens, "resume_cost_usd": cost}


def resume_additions(trajectory: cl.Trajectory) -> Iterator[tuple[float, int]]:
    """(tokens added, later main calls that read them) for each turn that resumes after a stop.

    The added tokens are the next call's context growth beyond the stop message's output and the text of the user
    steps between, which hold the prompt; the text is estimated at CHARS_PER_TOKEN.
    """
    steps = trajectory.steps
    main = [i for i, s in enumerate(steps) if is_main_call(s)]
    for k, (stop, resume) in enumerate(pairwise(main)):
        between = steps[stop + 1 : resume]
        if steps[stop].get("tool_calls") or not any(map(activity.is_prompt, between)):
            continue
        growth = steps[resume]["metrics"]["prompt_tokens"] - steps[stop]["metrics"]["prompt_tokens"]
        output = steps[stop]["metrics"].get("completion_tokens") or 0
        text = sum(len(str(s.get("message") or "")) for s in between if is_user_turn(s)) / CHARS_PER_TOKEN
        yield max(0.0, growth - output - text), len(main) - k - 2


def is_user_turn(step: dict) -> bool:
    return step.get("source") == "user" and not (step.get("extra") or {}).get("is_sidechain")


def token_rates(calls: list[dict]) -> tuple[float, float, float] | None:
    """USD per new input, cache-read, and output token, fitted by least squares to the per-call cost estimates.

    The calls of one trial share one price list, so the fit is exact up to rounding. None when fewer than three
    calls carry a cost or the token counts cannot separate the three rates.
    """
    rows = [
        (
            m["prompt_tokens"] - (m.get("cached_tokens") or 0),
            m.get("cached_tokens") or 0,
            m.get("completion_tokens") or 0,
        )
        for m in calls
        if m.get("cost_usd") is not None
    ]
    costs = [m["cost_usd"] for m in calls if m.get("cost_usd") is not None]
    if len(rows) < 3:
        return None
    normal = [[sum(r[i] * r[j] for r in rows) for j in range(3)] for i in range(3)]
    target = [sum(r[i] * c for r, c in zip(rows, costs, strict=True)) for i in range(3)]
    return solve(normal, target)


def solve(matrix: list[list[float]], target: list[float]) -> tuple[float, float, float] | None:
    """The solution of a 3x3 linear system by Cramer's rule; None when the system is singular."""
    det = determinant(matrix)
    scale = max(abs(v) for row in matrix for v in row) ** 3
    if not scale or abs(det) < 1e-12 * scale:
        return None
    columns = [[row[:j] + [t] + row[j + 1 :] for row, t in zip(matrix, target, strict=True)] for j in range(3)]
    x, y, z = (determinant(m) / det for m in columns)
    return x, y, z


def determinant(m: list[list[float]]) -> float:
    return (
        m[0][0] * (m[1][1] * m[2][2] - m[1][2] * m[2][1])
        - m[0][1] * (m[1][0] * m[2][2] - m[1][2] * m[2][0])
        + m[0][2] * (m[1][0] * m[2][1] - m[1][1] * m[2][0])
    )
