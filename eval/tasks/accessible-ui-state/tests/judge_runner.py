"""Run the rubric judges for one trial and write their answers.

Synced from eval/verifier/shared/judge_runner.py into every code task's tests/
by eval/scripts/sync_tests.py. Do not edit the copy under tests/.

test.sh runs it after the agent finishes, when the task has a rubric
(tests/rubric/items.json, which sync_tests.py resolves from
eval/verifier/rubrics/<task>.json). Each judge dimension gets one `claude -p`
call that sees only that dimension's items, the task instruction, the agent's
changes, and a blinded copy of the final workspace (build_view) as its working
directory. On a multi-step task every judge also sees the agent's reply that
each later turn answered, such as the proposal the user approved. Only the
report judge sees the agent's final message. A failed call is retried once.
The answers go to /logs/verifier/judge-items.json, and the rubric dimension
(tests/rubric/score.py) reads the score from there. When any call still fails,
or no item gets a yes or no, the trial gets no rubric score: the rubric
dimension and its weight are dropped, as consult_lib.prepare_tests drops them
when the judge cannot run, and lift.py compares that task without model scores
in both jobs.

The prompts are files beside score.py: system.md for every judge, and one
<dimension>.md per judge. Standard library only.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
from collections.abc import Mapping
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from itertools import pairwise
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import consult_lib as cl

WORKSPACE = Path("/app")
TESTS_DIR = Path("/tests")
RUBRIC_DIR = TESTS_DIR / "rubric"
OUTPUT_PATH = Path("/logs/verifier/judge-items.json")
TRANSCRIPT_DIR = Path("/logs/verifier/judge")

DIMENSIONS = ("structure", "scope", "boundaries", "proof", "report")
# Only the report judge checks the final message against the code. The others
# judge the code alone, so the agent's own description of it cannot sway them.
SEES_MESSAGE = frozenset({"report"})
ANSWERS = ("yes", "no", "unknown")
MET = ("yes", "no")
MUST_WEIGHT = 0.6
QUALITY_WEIGHT = 0.4

# Read-only file tools. --restricted removes every tool that runs commands and
# confines these to the working directory, which is the blinded view.
JUDGE_TOOLS = "Read,Grep,Glob"
DEFAULTS = {
    "CONSULT_JUDGE_MODEL": "claude-opus-5-5",
    "CONSULT_JUDGE_EFFORT": "high",
    "CONSULT_JUDGE_MAX_TURNS": "30",
    # Generous: Opus at high effort reading a large workspace can take minutes.
    # The verifier timeout in each code task's task.toml leaves room for three
    # rounds of two calls, plus a retry.
    "CONSULT_JUDGE_TIMEOUT_SEC": "900",
    # Judge calls per trial at once. With Harbor's default of 2 trials at once,
    # a run holds at most 4 judge calls open on the subscription.
    "CONSULT_JUDGE_CONCURRENCY": "2",
}
# The prompt's share of the changes; anything past it is left for the judge to read in the view.
CHANGES_LIMIT = 200_000
ATTEMPTS = 2
# Places Claude Code reads instructions or settings from whatever HOME is: the
# view's parent directories and the managed settings directories. The agent ran
# as root in this container, so it could have written any of them.
INSTRUCTION_NAMES = ("CLAUDE.md", "CLAUDE.local.md", "AGENTS.md", ".claude")
MANAGED_DIRS = (Path("/etc/claude-code"), Path("/Library/Application Support/ClaudeCode"))

# ------------------------------------------------------------------ blinding

# A phrase the bare arm could also write, so the replacement itself marks no arm.
NEUTRAL = "the project conventions"
SKIPPED_DIRS = frozenset({".git", "node_modules"})
# Renamed so the judge's Claude Code does not load them as its own instructions.
RENAMED_FILES = {"CLAUDE.md": "CLAUDE.md.txt", "CLAUDE.local.md": "CLAUDE.local.md.txt", "AGENTS.md": "AGENTS.md.txt"}
RENAMED_DIRS = {".claude": "dot-claude"}
VIEW_FILE_LIMIT = 1_000_000
_SKILLS = "|".join(sorted(map(re.escape, cl.CONSULT_SKILLS), key=len, reverse=True))
# Text that would tell a judge which arm wrote the code. Both arms get the same
# replacements. The calibration runs (2026-11-02) showed docs/plans/ in consult
# workspaces and "fresh-context review" in consult messages; the rest are the
# names Consult gives its own parts. Each NEUTRAL pattern takes a leading
# article with it, so "the proof skill" reads "the project conventions".
_ARTICLE = r"(?:\b(?:[Tt]he|[Aa]n?)\s+)?"
_RULE = r"[Rr]ules?\s+\d+"
SCRUBS = (
    (re.compile(_ARTICLE + r"(?:[\w.~-]*/)*skills/[a-z][a-z0-9-]*/SKILL\.md"), NEUTRAL),
    (re.compile(_ARTICLE + rf"/?\bconsult:(?:{_SKILLS})\b"), NEUTRAL),
    (re.compile(rf"\b{_RULE}\s+of\s+(?:the\s+)?`?(?:{_SKILLS})`?(?:\s+skill)?\b"), NEUTRAL),
    (
        re.compile(
            _ARTICLE
            + rf"`?\b(?:{_SKILLS})\b`?(?:(?:,|\s+and|\s+or)\s+`?(?:{_SKILLS})\b`?)*"
            + rf"\s+(?:skills?(?:'s)?(?:\s+{_RULE})?|{_RULE})\b"
        ),
        NEUTRAL,
    ),
    (re.compile(_ARTICLE + rf"\b(?:Consult(?:'s)?\s+)?[Cc]ore\s+{_RULE}"), NEUTRAL),
    (re.compile(_ARTICLE + r"\b[Cc]onsult(?:'s)?\s+[Cc]ore\b"), NEUTRAL),
    (re.compile(_ARTICLE + r"\bIron Law\b"), NEUTRAL),
    (re.compile(_ARTICLE + r"\bConsult(?:'s)?\b"), NEUTRAL),
    (re.compile(r"\bfresh[- ]context\b"), "separate"),
    (re.compile(r"\bdocs/plans\b"), "docs/notes"),
)


def scrub(text: str) -> str:
    """The text with every SCRUBS pattern replaced, in order."""
    for pattern, replacement in SCRUBS:
        text = pattern.sub(replacement, text)
    return text


def view_rel(rel: Path) -> Path:
    """Where a workspace path lands in the view: instruction files renamed, docs/plans as docs/notes."""
    parts = [RENAMED_DIRS.get(part, part) for part in rel.parts[:-1]] + [RENAMED_FILES.get(rel.name, rel.name)]
    for i in range(len(parts) - 1):
        if parts[i] == "docs" and parts[i + 1] == "plans":
            parts[i + 1] = "notes"
    return Path(*parts)


def build_view(workspace: Path, dest: Path) -> list[str]:
    """Copy the workspace to dest, blinded; return the workspace paths left out.

    Leaves out .git, node_modules, symlinks (their target may be any container
    file), and files over VIEW_FILE_LIMIT. Text files are scrubbed; other files
    are copied as they are. A renamed path that collides with an existing one
    gets a numbered suffix, so no file is lost.
    """
    left_out: list[str] = []
    dest.mkdir(parents=True)
    for root, dirs, files in os.walk(workspace):
        dirs[:] = sorted(d for d in dirs if d not in SKIPPED_DIRS and not (Path(root) / d).is_symlink())
        for name in sorted(files):
            source = Path(root) / name
            rel = source.relative_to(workspace)
            if source.is_symlink() or not source.is_file() or source.stat().st_size > VIEW_FILE_LIMIT:
                left_out.append(str(rel))
                continue
            target = free_path(dest / view_rel(rel))
            target.parent.mkdir(parents=True, exist_ok=True)
            data = source.read_bytes()
            try:
                target.write_text(scrub(data.decode("utf-8")), encoding="utf-8")
            except UnicodeDecodeError:
                target.write_bytes(data)
    return left_out


def free_path(path: Path) -> Path:
    """path, or path with the first free .2, .3, ... suffix when it exists."""
    candidate, n = path, 2
    while candidate.exists():
        candidate = path.with_name(f"{path.name}.{n}")
        n += 1
    return candidate


# ------------------------------------------------------------------- prompts


@dataclass(frozen=True)
class Config:
    model: str
    effort: str
    max_turns: int
    timeout_sec: int
    concurrency: int

    @classmethod
    def from_env(cls, environ: Mapping[str, str]) -> Config:
        value = {key: environ.get(key) or default for key, default in DEFAULTS.items()}
        return cls(
            model=value["CONSULT_JUDGE_MODEL"],
            effort=value["CONSULT_JUDGE_EFFORT"],
            max_turns=int(value["CONSULT_JUDGE_MAX_TURNS"]),
            timeout_sec=int(value["CONSULT_JUDGE_TIMEOUT_SEC"]),
            concurrency=max(1, int(value["CONSULT_JUDGE_CONCURRENCY"])),
        )


@dataclass(frozen=True)
class Inputs:
    """What every judge of one trial is shown, already scrubbed."""

    instruction: str
    changes: str
    final_message: str
    # (heading, the agent's reply a later turn answered), for multi-step tasks.
    earlier_replies: tuple[tuple[str, str], ...] = ()


def item_text(item: dict) -> str:
    """One item as the judge reads it.

    The tier is left out so it cannot weigh on the answer. So is the rule's key
    phrase: the Consult arm often repeats rule wording in its code and notes,
    and a judge shown that wording would reward the echo, not the code.
    """
    return "\n".join(
        [
            f"### {item['id']}",
            "",
            f"- Question: {item['question']}",
            f"- Where to look: {item['look_at']}",
            f"- Answer yes when: {item['yes_when']}",
            f"- Answer no when: {item['no_when']}",
            "",
        ]
    )


def changes_section(changes: str) -> str:
    if len(changes) <= CHANGES_LIMIT:
        return changes
    note = "\n\n[The changes are cut here. Read the rest from the files in your working directory.]"
    return changes[:CHANGES_LIMIT] + note


def replies_shown(dimension: str, inputs: Inputs) -> tuple[tuple[str, str], ...]:
    """The agent's earlier replies a judge reads.

    The report judge reads them all: the report can span turns, and it checks
    the build against what the agent proposed and the user approved. A code
    judge reads none, so the agent's description of its own work cannot sway
    it; an agent that builds in the first turn would otherwise have its report
    read as the approved proposal.
    """
    return inputs.earlier_replies if dimension in SEES_MESSAGE else ()


def dimension_prompt(dimension: str, items: list[dict], inputs: Inputs, guidance: str) -> str:
    """The user prompt for one judge: its guidance, the task, its items, then the fenced agent output."""
    output = []
    for heading, reply in replies_shown(dimension, inputs):
        output += [f"## {heading}", "", reply or "No message.", ""]
    output += ["## The agent's changes", "", changes_section(inputs.changes)]
    if dimension in SEES_MESSAGE:
        output += ["", "## The agent's final message to the user", "", inputs.final_message or "No final message."]
    return "\n".join(
        [
            guidance.strip(),
            "",
            "# The task the agent was given",
            "",
            inputs.instruction.strip(),
            "",
            "# Your items",
            "",
            *map(item_text, items),
            "# The agent's output",
            "",
            "Your working directory holds the full workspace after the change. Read it with Read, Grep, and Glob.",
            "",
            cl.BUNDLE_START,
            cl.fenced_text("\n".join(output)),
            cl.BUNDLE_END,
            "",
        ]
    )


def answer_schema(items: list[dict]) -> dict:
    """One answer per item id: yes, no, or unknown, with evidence and a short reason."""
    ids = [item["id"] for item in items]
    answer = {
        "type": "object",
        "properties": {
            "id": {"type": "string", "enum": ids},
            "answer": {"type": "string", "enum": list(ANSWERS)},
            "evidence": {"type": "string"},
            "why": {"type": "string"},
        },
        "required": ["id", "answer", "evidence", "why"],
        "additionalProperties": False,
    }
    return {
        "type": "object",
        "properties": {"answers": {"type": "array", "items": answer, "minItems": len(ids), "maxItems": len(ids)}},
        "required": ["answers"],
        "additionalProperties": False,
    }


# --------------------------------------------------------------------- calls


def claude_argv(schema: dict, system_prompt: str, config: Config) -> list[str]:
    """The judge's `claude -p` command. The prompt goes on stdin.

    Checked against the Claude Code CLI reference and the 2.1.282 CLI pinned in
    verifier/shared/Dockerfile (2026-11-02): --restricted removes every tool
    that runs commands, confines file tools to the working directory, and
    ignores user, project, and local settings, so no hook or plugin loads.
    --strict-mcp-config adds no MCP server, --disable-slash-commands loads no
    skill, and dontAsk denies anything that would prompt. --bare is not used
    because it cannot read a subscription token.
    """
    return [
        "claude",
        "-p",
        "--output-format",
        "stream-json",
        "--verbose",
        "--json-schema",
        json.dumps(schema),
        "--system-prompt",
        system_prompt,
        "--model",
        config.model,
        "--effort",
        config.effort,
        "--tools",
        JUDGE_TOOLS,
        "--restricted",
        "--strict-mcp-config",
        "--disable-slash-commands",
        "--permission-mode",
        "dontAsk",
        "--no-session-persistence",
        "--max-turns",
        str(config.max_turns),
    ]


def judge_env(environ: Mapping[str, str], home: Path) -> dict[str, str]:
    """A clean environment: an empty home and config dir, and one credential.

    The subscription token wins over an API key when both are set, as
    CLAUDE_FORCE_OAUTH makes the agent do, so a judge call never bills the API
    by accident.
    """
    env = {
        "PATH": environ.get("PATH") or "/usr/local/bin:/usr/bin:/bin",
        "HOME": str(home),
        "CLAUDE_CONFIG_DIR": str(home / ".claude"),
        "LANG": "C.UTF-8",
        "DISABLE_AUTOUPDATER": "1",
    }
    if environ.get("CLAUDE_CODE_OAUTH_TOKEN"):
        env["CLAUDE_CODE_OAUTH_TOKEN"] = environ["CLAUDE_CODE_OAUTH_TOKEN"]
    elif environ.get("ANTHROPIC_API_KEY"):
        env["ANTHROPIC_API_KEY"] = environ["ANTHROPIC_API_KEY"]
    return env


def stream_lines(stream: str) -> list[dict]:
    lines = []
    for line in stream.splitlines():
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            lines.append(value)
    return lines


def parse_result(stream: str) -> tuple[dict, str | None]:
    """The call's final result message and its error, if any. Never raises."""
    lines = stream_lines(stream)
    results = [line for line in lines if line.get("type") == "result"]
    if not results:
        return {}, "the call ended without a result message"
    result = results[-1]
    if result.get("is_error"):
        return result, f"the call failed: {str(result.get('result'))[:300]}"
    if not isinstance(result.get("structured_output"), dict):
        return result, "the call returned no structured output"
    return result, None


def cli_version(stream: str) -> str | None:
    for line in stream_lines(stream):
        if line.get("type") == "system" and line.get("subtype") == "init":
            return line.get("claude_code_version")
    return None


def parse_answers(structured: dict | None, items: list[dict]) -> list[dict]:
    """One record per item, in item order. Never raises.

    An item the judge skipped, answered twice, or answered outside the schema
    is recorded as unknown with source "missing" or "invalid", apart from the
    unknowns the judge chose (source "judge").
    """
    ids = {item["id"] for item in items}
    entries = (structured or {}).get("answers")
    seen: dict[str, dict] = {}
    invalid: set[str] = set()
    for entry in entries if isinstance(entries, list) else []:
        item_id = entry.get("id") if isinstance(entry, dict) else None
        if not isinstance(item_id, str) or item_id not in ids:
            continue
        if item_id in seen or entry.get("answer") not in ANSWERS:
            invalid.add(item_id)
        seen.setdefault(item_id, entry)
    return [record(item, seen.get(item["id"]), item["id"] in invalid) for item in items]


def record(item: dict, entry: dict | None, invalid: bool) -> dict:
    base = {key: item[key] for key in ("id", "dimension", "tier", "polarity", "rules")}
    if entry is None or invalid:
        source = "invalid" if invalid else "missing"
        return {**base, "answer": "unknown", "source": source, "evidence": "", "why": ""}
    text = {key: str(entry.get(key) or "") for key in ("evidence", "why")}
    return {**base, "answer": entry["answer"], "source": "judge", **text}


def met_rate(records: list[dict], tier: str) -> float | None:
    answered = [r for r in records if r["tier"] == tier and r["answer"] in MET]
    if not answered:
        return None
    return sum(r["answer"] == "yes" for r in answered) / len(answered)


def score(records: list[dict]) -> float | None:
    """Must-have met rate x 0.6 plus quality met rate x 0.4, leaving unknowns out.

    A tier with no yes or no answer drops out and the other tier is the score.
    None when no item has a yes or no answer.
    """
    must, quality = met_rate(records, "must"), met_rate(records, "quality")
    if must is None and quality is None:
        return None
    if must is None:
        return round(quality, 4)
    if quality is None:
        return round(must, 4)
    return round(MUST_WEIGHT * must + QUALITY_WEIGHT * quality, 4)


@dataclass(frozen=True)
class RunContext:
    config: Config
    view: Path
    env: dict[str, str]
    transcripts: Path


def judge_dimension(
    dimension: str, items: list[dict], prompts: dict[str, str], inputs: Inputs, run: RunContext
) -> dict:
    """Run one judge, retrying a failed call once; return its call record with an answer record per item."""
    argv = claude_argv(answer_schema(items), prompts["system"], run.config)
    prompt = dimension_prompt(dimension, items, inputs, prompts[dimension])
    run.transcripts.mkdir(parents=True, exist_ok=True)
    for attempt in range(1, ATTEMPTS + 1):
        stream, error = call_claude(argv, prompt, run)
        (run.transcripts / f"{dimension}.{attempt}.jsonl").write_text(stream)
        result, parse_error = parse_result(stream)
        error = error or parse_error
        if error is None:
            break
    return {
        "dimension": dimension,
        "error": error,
        "attempts": attempt,
        "cli_version": cli_version(stream),
        "num_turns": result.get("num_turns"),
        "duration_ms": result.get("duration_ms"),
        "usage": result.get("usage"),
        "total_cost_usd": result.get("total_cost_usd"),
        "answers": parse_answers(None if error else result.get("structured_output"), items),
    }


def call_claude(argv: list[str], prompt: str, run: RunContext) -> tuple[str, str | None]:
    """One `claude -p` call in the view: its stdout, and an error when it timed out or could not start."""
    try:
        proc = subprocess.run(
            argv,
            cwd=run.view,
            env=run.env,
            input=prompt,
            capture_output=True,
            text=True,
            timeout=run.config.timeout_sec,
            check=False,
        )
    except subprocess.TimeoutExpired as expired:
        out = expired.stdout or ""
        stream = out.decode(errors="replace") if isinstance(out, bytes) else out
        return stream, f"the call timed out after {run.config.timeout_sec}s"
    except OSError as error:
        return "", f"the call could not start: {error}"
    return proc.stdout, None


def planted_instructions(view: Path) -> list[str]:
    """Instruction or settings files the judge's Claude Code could load from outside its view."""
    found = [str(parent / name) for parent in view.parents for name in INSTRUCTION_NAMES if (parent / name).exists()]
    return found + [str(path) for path in MANAGED_DIRS if path.exists()]


def load_prompts(rubric_dir: Path, dimensions: list[str]) -> dict[str, str]:
    return {name: (rubric_dir / f"{name}.md").read_text() for name in ["system", *dimensions]}


def judge_trial(
    workspace: Path, rubric_dir: Path, transcripts: Path, environ: Mapping[str, str], steps: list[dict]
) -> dict:
    """Judge one finished workspace against its rubric; returns what judge-items.json holds.

    steps are the trajectory's steps, for the final message and the replies
    earlier turns answered.
    """
    items = json.loads((rubric_dir / "items.json").read_text())["items"]
    dimensions = [d for d in DIMENSIONS if any(item["dimension"] == d for item in items)]
    prompts = load_prompts(rubric_dir, dimensions)
    instruction = (rubric_dir / "instruction.md").read_text()
    inputs = Inputs(
        instruction=instruction,
        changes=scrub(changed_paths_text(workspace) + cl.changes_text(workspace)),
        final_message=scrub(cl.final_agent_message(cl.Trajectory(steps=steps, calls=[]))),
        earlier_replies=tuple((heading, scrub(reply)) for heading, reply in earlier_replies(instruction, steps)),
    )
    config = Config.from_env(environ)
    with tempfile.TemporaryDirectory(prefix="judge-") as tmp:
        view, home = Path(tmp) / "workspace", Path(tmp) / "home"
        left_out = build_view(workspace, view)
        home.mkdir()
        run = RunContext(config=config, view=view, env=judge_env(environ, home), transcripts=transcripts)
        planted = planted_instructions(view)
        if planted:
            calls = [refused(d, items, planted) for d in dimensions]
        else:
            with ThreadPoolExecutor(max_workers=config.concurrency) as pool:
                calls = list(
                    pool.map(
                        lambda d: judge_dimension(d, [i for i in items if i["dimension"] == d], prompts, inputs, run),
                        dimensions,
                    )
                )
    records = [answer for call in calls for answer in call.pop("answers")]
    complete = all(call["error"] is None for call in calls)
    return {
        "model": config.model,
        "effort": config.effort,
        "max_turns": config.max_turns,
        "complete": complete,
        "score": score(records) if complete else None,
        "unknown": sum(r["answer"] == "unknown" for r in records),
        "left_out_of_view": left_out,
        "calls": calls,
        "items": records,
    }


def refused(dimension: str, items: list[dict], planted: list[str]) -> dict:
    """The call record for a judge not started because files outside the view could steer it."""
    error = f"not run: the judge could load {', '.join(planted)}"
    answers = parse_answers(None, [i for i in items if i["dimension"] == dimension])
    return {"dimension": dimension, "error": error, "attempts": 0, "answers": answers}


TURN_RE = cl.TURN_RE
same_start = cl.same_start


def earlier_replies(instruction: str, steps: list[dict]) -> list[tuple[str, str]]:
    """For each turn after the first, the agent's last message before that turn's user message.

    The final step's trajectory holds the whole resumed session, so the reply
    the approval turn answered (the proposal) is the last agent message before
    the approval message. A single-step instruction has no turns and yields [].
    """
    turns = TURN_RE.findall(instruction)
    replies = []
    for (_, previous, _), (number, name, text) in pairwise(turns):
        start = next(
            (i for i, step in enumerate(steps) if step.get("source") == "user" and same_start(step, text)), None
        )
        if start is None:
            continue
        messages = [str(step.get("message") or "") for step in steps[:start] if step.get("source") == "agent"]
        reply = next((m for m in reversed(messages) if m.strip()), "")
        replies.append(
            (f"The agent's reply at the end of the {previous} turn, which turn {number} ({name}) answered", reply)
        )
    return replies


def changed_paths_text(workspace: Path) -> str:
    """Every changed path with its git status, and where it sits in the view when blinding moved it."""
    sha = cl.scaffold_sha(workspace)
    lines = [line.split("\t") for line in cl.git(workspace, "diff", "--name-status", sha).splitlines() if line]
    lines += [["A", path] for path in cl.git(workspace, "ls-files", "--others", "--exclude-standard").splitlines()]
    rows = []
    for status, *paths in lines:
        path = paths[-1]
        moved = view_rel(Path(path))
        where = (
            f" (in your working directory as {moved})"
            if str(moved) != scrub(path) and not status.startswith("D")
            else ""
        )
        rows.append(f"- {status[0]} {path}{where}")
    return "\n".join(["# Changed paths (A added, M modified, D deleted, R renamed)", "", *rows, "", ""])


def main(argv: list[str]) -> int:
    if argv[1:]:
        sys.stderr.write("usage: judge_runner.py (reads /app, /tests/rubric, /logs/agent; writes /logs/verifier)\n")
        return 2
    steps = cl.load_trajectory().steps
    result = judge_trial(WORKSPACE, RUBRIC_DIR, TRANSCRIPT_DIR, os.environ, steps)
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(result, indent=2) + "\n")
    for call in result["calls"]:
        if call["error"]:
            sys.stderr.write(f"consult: {call['dimension']} judge: {call['error']}\n")
    if result["score"] is None:
        cl.drop_dimension(TESTS_DIR, "rubric")
        why = "a judge call failed" if not result["complete"] else "no rubric item got a yes or no"
        sys.stderr.write(f"consult: {why}; reward excludes the rubric (judge-items.json has the details)\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
