"""Where an agent's time and output tokens go, by kind of tool call, for the lift report's activity table.

lift.py calls trial_activity() and words_per_stop() on each trial's final-step trajectory. With resume_trajectory
that trajectory holds the whole session, so nothing is counted twice.

Every tool call counts once under its category (CATEGORIES). Output tokens and time are per agent step, so each step
is charged to the category of its first tool call, or to messages when it made none. A gap between two steps goes to
the latest agent step in the turn; a gap that starts at a prompt goes to the step that answers it. A gap that ends at
a prompt is left out: that is the eval waiting, not the agent working. A step with parallel tool calls charges all its
time to its first call, so seconds per category are approximate.

A step's timestamp marks when the model finished writing it, so the gap after a call holds the call's run time and
then the model's time to think and write the next step. A category's seconds therefore include the model's time to
produce the step after each of its calls, and messages, which end a turn, get no seconds of their own. Splitting a
gap at the tool result needs Claude Code's session logs, which most saved jobs lack, so the gaps stay whole.

A shell call is read by its commands, not its whole text: heredoc bodies and quoted strings are blanked first, so a
test command named in a file's content, a commit message, or a grep pattern is not a run. A script the call writes to
a file and then runs with an interpreter counts as part of the call (scratch_scripts).
"""

from __future__ import annotations

import dataclasses
import re
import sys
from collections.abc import Iterator
from datetime import datetime
from itertools import chain
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "verifier" / "shared"))
import consult_lib as cl
import consult_rules as cr
import house_rules as hr

CATEGORIES = {
    "test_targeted": "targeted test runs",
    "test_suite": "whole-suite test runs",
    "edit_test": "edit-and-test scripts",
    "break_restore": "break-and-restore scripts",
    "static": "static checks",
    "read": "reads",
    "write_test": "test writes",
    "write_spec": "spec writes",
    "write_other": "source and other writes",
    "git": "git",
    "skill": "skill loads and references",
    "subagent": "subagents",
    "message": "messages",
    "other": "other tool calls",
}
MEASURES = ("calls", "seconds", "output_tokens")
# A test run aimed at one file, folder, or test name rather than the whole suite.
TARGETED_TEST_RE = re.compile(
    r"\.(test|spec)\.[cm]?[jt]sx?\b|(^|\s)(tests?|__tests__)/\S|--test-name-pattern|--grep\b|\s-t\s"
)
READ_COMMAND_RE = re.compile(r"cat|ls|find|grep|rg|head|tail|sed|wc|awk|tree|less|file|stat|diff|jq")
# Commands that set up or print rather than do the call's work, and the loop and branch words before a command.
LEAD_SKIPPED = frozenset({"cd", "set", "export", "echo", "printf", "for", "done", "fi", "esac"})
LEAD_KEYWORDS = frozenset({"do", "then", "else", "if", "while", "until", "!", "{", "time"})
# git commands that only look; one after a read or a server check does not make the call a git call.
GIT_CHECKS = frozenset({"status", "diff", "log", "show"})
# A whole-line shell comment. consult_lib's quote masking does not know comments.
COMMENT_LINE_RE = re.compile(r"^[ \t]*#.*$", re.MULTILINE)
# OpenAPI linters, which hr.STATIC_CHECKS does not list.
SPEC_LINT_RE = re.compile(r"(@redocly/cli|\bredocly|\bspectral)\S*\s+lint\b")
# Interpreters that run a script file; a shell runs the file's commands.
SCRIPT_RUNNERS = frozenset({"node", "python", "python3", "bash", "sh"})
SHELLS = frozenset({"bash", "sh"})
# Putting source back inside one shell call: git checkout, restore, or stash, or a copy back from /tmp or a backup,
# by cp or mv or by a script's copyFileSync(f + ".orig", f) or shutil.copy("/tmp/a.ts", p).
RESTORE_COMMAND_RE = re.compile(
    r"\bgit\s+(checkout(?!\s+-[bB]\b)|restore|stash)\b|\b(cp|mv)\s+(-\w+\s+)*(/tmp/|\S+\.(bak|orig)\b)"
    r"|\b(copyFileSync|copyfile|copy2?|move)\(\s*[^,)]*(/tmp/|\.(bak|orig)\b)"
)
# A command a node or python script starts as a child process, such as execSync("npm test 2>&1").
PROCESS_COMMAND_RE = re.compile(
    r"\b(?:execSync|execFileSync|spawnSync|system|run|check_output|check_call)\(\s*[`'\"]([^`'\"]*)"
)
# A scratch file written outside the repo, such as `cat > /tmp/probe.mjs <<EOF`, is a probe, not a read.
PROBE_COMMAND_RE = re.compile(r"^\s*(cd\s+\S+\s*(&&|;)\s*)?cat\s*>")
# A skill's body or one of its reference files, read by path.
SKILL_FILE_RE = re.compile(r"skills/[\w:-]+/(SKILL\.md|references/)")
# Claude Code tells the agent a background subagent finished with a user step that starts with this tag.
TASK_NOTIFICATION_RE = re.compile(r"\s*<task-notification>")
READ_TOOLS = frozenset({"Read", "Grep", "Glob", "LS", "NotebookRead"})
SUBAGENT_TOOLS = frozenset({"Agent", "Task"})


def call_category(call: cl.ToolCall) -> str:
    """The CATEGORIES key for one tool call."""
    if call.name == "Skill" or reads_skill_file(call):
        return "skill"
    if call.name in SUBAGENT_TOOLS:
        return "subagent"
    if cl.is_command_call(call):
        return command_category(call)
    if cl.is_write_call(call):
        return write_category(cl.written_paths(call))
    return "read" if call.name in READ_TOOLS else "other"


def command_category(call: cl.ToolCall) -> str:
    """A shell call's category. Writes come before tests and static checks: a script that edits files and then
    runs the tests is an edit-and-test script, or a break-and-restore script when it also puts source back. A test
    run is targeted when one of its own test commands names a test file, folder, or test name."""
    call = uncommented(call)
    parts = [call, *filter(None, [scratch_scripts(call)])]
    text = "\n".join(map(cl.command_text, parts))
    writes = [path for part in parts for path in cl.written_paths(part)]
    tests = [segment for part in parts for segment in test_runs(part)]
    if tests and writes:
        return "break_restore" if RESTORE_COMMAND_RE.search(text) else "edit_test"
    if writes:
        return write_category(writes)
    if tests:
        return "test_targeted" if any(TARGETED_TEST_RE.search(segment) for segment in tests) else "test_suite"
    commands = shell_mask(call)
    if SPEC_LINT_RE.search(commands) or any(check.search(commands) for check in hr.STATIC_CHECKS.values()):
        return "static"
    if is_git_call(call):
        return "git"
    if PROBE_COMMAND_RE.search(text):
        return "other"
    return "read" if READ_COMMAND_RE.fullmatch(lead_command(call)) else "other"


def uncommented(call: cl.ToolCall) -> cl.ToolCall:
    """The shell call with whole-line comments blanked outside heredoc bodies, keeping offsets. Otherwise an
    apostrophe in `# today's prices` opens a quote for consult_lib's masking and hides the commands after it."""
    text = cl.command_text(call)
    bodies = [match.span(4) for match in cl.HEREDOC_RE.finditer(text)]

    def blank(comment: re.Match) -> str:
        inside = any(start <= comment.start() < end for start, end in bodies)
        return comment[0] if inside else " " * len(comment[0])

    return dataclasses.replace(call, arguments={"command": COMMENT_LINE_RE.sub(blank, text)})


def shell_mask(call: cl.ToolCall) -> str:
    """A shell call's text with heredoc bodies and quoted strings blanked, keeping offsets: only its commands."""
    return mask_quotes(cl._shell_source(cl.command_text(call)))


def mask_quotes(text: str) -> str:
    """Quoted text blanked to underscores, keeping the quotes and offsets. Unlike cl._mask_quotes, a command
    substitution inside double quotes keeps its commands, since it runs (`echo "$(node --test)"`), and quotes inside
    it nest (`H="$(curl -d "{}")"`). A quote with no closing quote is left as it is."""
    out = list(text)
    scan_shell(text, out, 0, nested=False)
    return "".join(out)


def scan_shell(text: str, out: list[str], index: int, nested: bool) -> int:
    """Blank quoted text into out from index, as shell code; inside `$(...)` (nested), stop after its closing
    parenthesis. Returns the index scanning stopped at."""
    depth = 0
    while index < len(text):
        char = text[index]
        if char == "\\":
            index += 2
            continue
        closing = text.find(char, index + 1) if char in "'\"" else -1
        if char == "'" and closing != -1:
            out[index + 1 : closing] = "_" * (closing - index - 1)
            index = closing
        elif char == '"' and closing != -1:
            index = scan_double_quoted(text, out, index + 1) - 1
        elif nested and char in "()":
            depth += 1 if char == "(" else -1
            if depth < 0:
                return index + 1
        index += 1
    return index


def scan_double_quoted(text: str, out: list[str], index: int) -> int:
    """Blank a double-quoted string's text into out from index, scanning any `$(...)` in it as shell code. Returns
    the index after its closing quote."""
    while index < len(text) and text[index] != '"':
        if text.startswith("$(", index):
            index = scan_shell(text, out, index + 2, nested=True)
            continue
        width = 2 if text[index] == "\\" else 1
        out[index : index + width] = "_" * len(out[index : index + width])
        index += width
    return index + 1


def test_runs(call: cl.ToolCall) -> list[str]:
    """The test commands a shell call runs: its shell segments that run tests, from shell_mask(), so
    `grep "node --test"`, a commit message, or a README heredoc that names a test command is not a run; and the test
    commands an inline node or python script starts as a child process."""
    segments = cl.SHELL_SEGMENT_RE.findall(shell_mask(call))
    started = chain.from_iterable(PROCESS_COMMAND_RE.findall(body) for body in script_bodies(cl.command_text(call)))
    return [command for command in chain(segments, started) if cr.TEST_COMMAND_RE.search(command)]


def lead_command(call: cl.ToolCall) -> str:
    """The first command a shell call runs, past `cd`, `set`, `export`, `echo`, variable assignments, and loop and
    branch words, so `for f in a b; do cat -n $f; done` leads with cat. Empty when there is none."""
    for words in cl.shell_commands(call):
        while words and words[0] in LEAD_KEYWORDS:
            words = words[1:]
        words = [word for word in words if not cl.ASSIGNMENT_RE.fullmatch(word)] if words[:1] != ["for"] else []
        if words and words[0] not in LEAD_SKIPPED:
            return words[0]
    return ""


def is_git_call(call: cl.ToolCall) -> bool:
    """git leads the call, or the call runs a git command that does more than look (GIT_CHECKS)."""
    invocations = cl.git_invocations(call)
    return bool(invocations) and (
        lead_command(call) == "git" or any(i.subcommand not in GIT_CHECKS for i in invocations)
    )


def scratch_scripts(call: cl.ToolCall) -> cl.ToolCall | None:
    """The scripts a shell call writes from a heredoc and then runs, as one shell call of their own, or None.

    `cat > /tmp/edit.mjs <<'EOF' ... EOF` then `node /tmp/edit.mjs` edits files that cl.written_paths does not see,
    since the script is a file, not inline. Here a node or python script becomes an inline heredoc script and a bash
    or sh script becomes its own commands, with the call's `cd` commands kept in order, so cl.written_paths and
    test_runs read them as they read inline code.
    """
    files = dict(heredoc_files(cl.command_text(call)))
    program = []
    for words in cl.shell_commands(call) if files else []:
        if words[:1] == ["cd"]:
            program.append(" ".join(words))
            continue
        script = next((files[path] for path in (w.strip("'\"") for w in words[1:]) if path in files), None)
        if words[0] in SCRIPT_RUNNERS and script is not None:
            program.append(script if words[0] in SHELLS else f"{words[0]} - <<'SCRIPT'\n{script}\nSCRIPT")
    if all(line.startswith("cd ") for line in program):
        return None
    return uncommented(
        cl.ToolCall(step_index=call.step_index, name=call.name, arguments={"command": "\n".join(program)})
    )


def heredocs(text: str) -> Iterator[tuple[str, str]]:
    """(command, body) for each heredoc: the shell command that reads it, from its line, and its body."""
    for match in cl.HEREDOC_RE.finditer(text):
        before = text[text.rfind("\n", 0, match.start()) + 1 : match.start()]
        yield re.split(r"[;&|]", before)[-1] + match[1], match[4]


def heredoc_files(text: str) -> Iterator[tuple[str, str]]:
    """(path, body) for each heredoc that `cat > path` or `tee path` writes to a file."""
    for command, body in heredocs(text):
        target = cl.REDIRECT_TARGET_RE.search(command)
        if command.split()[:1] in (["cat"], ["tee"]) and target:
            yield (target[1] or target[2]).strip("'\""), body


def script_bodies(text: str) -> list[str]:
    """The heredoc bodies an interpreter runs as inline scripts, such as `python3 - <<'EOF'`."""
    return [body for command, body in heredocs(text) if command.split()[:1] and command.split()[0] in cl.INTERPRETERS]


def reads_skill_file(call: cl.ToolCall) -> bool:
    """A read of a skill's body or reference file by path, which loads skill text like a Skill call does."""
    if call.name in READ_TOOLS:
        target = str(call.arguments.get("file_path") or call.arguments.get("path") or "")
    elif cl.is_command_call(call) and READ_COMMAND_RE.fullmatch(lead_command(uncommented(call))):
        target = cl.command_text(call)
    else:
        return False
    return bool(SKILL_FILE_RE.search(target))


def write_category(paths: list[str]) -> str:
    """A write's category from the paths it wrote: a test file, else a contract (spec, schema, or types), else
    anything else."""
    if any(cl.classify(p) == "test" for p in paths):
        return "write_test"
    if any(hr.CONTRACT_PATH_RE.search(p) for p in paths):
        return "write_spec"
    return "write_other"


def is_prompt(step: dict) -> bool:
    """A user turn: the eval's brief, approval, or continue. Skill bodies and background-task notices that Claude Code
    injects as user steps are not."""
    if step.get("source") != "user" or (step.get("extra") or {}).get("is_sidechain"):
        return False
    message = str(step.get("message") or "")
    return not (cl.SKILL_BASE_DIR_RE.match(message) or TASK_NOTIFICATION_RE.match(message))


def step_categories(trajectory: cl.Trajectory) -> dict[int, str]:
    """Agent step index -> the category of its first tool call, or messages when it made none."""
    first: dict[int, str] = {}
    for call in trajectory.calls:
        first.setdefault(call.step_index, call_category(call))
    return {i: first.get(i, "message") for i, s in enumerate(trajectory.steps) if s.get("source") == "agent"}


def trial_activity(trajectory: cl.Trajectory) -> dict[str, dict[str, float]]:
    """category -> calls, seconds, and output tokens for one trial.

    Output tokens come from each step's metrics and are 0 for a trajectory that records none.
    """
    totals = {c: dict.fromkeys(MEASURES, 0.0) for c in CATEGORIES}
    for call in trajectory.calls:
        totals[call_category(call)]["calls"] += 1
    categories = step_categories(trajectory)
    for index, category in categories.items():
        totals[category]["output_tokens"] += output_tokens(trajectory.steps[index])
        if category == "message":
            totals[category]["calls"] += 1
    for category, seconds in working_gaps(trajectory.steps, categories):
        totals[category]["seconds"] += seconds
    return totals


def output_tokens(step: dict) -> float:
    return float((step.get("metrics") or {}).get("completion_tokens") or 0)


def working_gaps(steps: list[dict], categories: dict[int, str]) -> Iterator[tuple[str, float]]:
    """(category, seconds) for each gap between steps that the agent spent working; see the module docstring."""
    current: str | None = None
    for index in range(len(steps) - 1):
        if is_prompt(steps[index]):
            current = categories.get(index + 1)
        current = categories.get(index, current)
        seconds = elapsed(steps[index], steps[index + 1])
        if current is not None and seconds is not None and not is_prompt(steps[index + 1]):
            yield current, seconds


def elapsed(step: dict, following: dict) -> float | None:
    """Seconds from one step's timestamp to the next; None when either lacks one or the clock runs backward."""
    if not step.get("timestamp") or not following.get("timestamp"):
        return None
    seconds = (
        datetime.fromisoformat(following["timestamp"]) - datetime.fromisoformat(step["timestamp"])
    ).total_seconds()
    return seconds if seconds >= 0 else None


def words_per_stop(trajectory: cl.Trajectory) -> float | None:
    """Mean words in the last message of each turn, the text a person reads when the agent stops; None without one."""
    starts = [i for i, s in enumerate(trajectory.steps) if is_prompt(s)]
    ends = [*starts[1:], len(trajectory.steps)]
    lengths = [len(m.split()) for m in (hr.last_message_in(trajectory, span) for span in zip(starts, ends)) if m]
    return sum(lengths) / len(lengths) if lengths else None
