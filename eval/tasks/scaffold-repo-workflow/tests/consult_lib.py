"""Shared verifier helpers for Consult Harbor tasks.

Synced from eval/verifier/shared/consult_lib.py into every task's tests/ by
eval/scripts/sync_tests.py. Do not edit the copy under tests/.

Pure helpers over the workspace (/app) and the ATIF trajectory
(/logs/agent/trajectory.json). Dimension scripts under tests/<dim>/ import this
module and register their own rewardkit criteria. Standard library only, so
`python3 consult_lib.py bundle` also runs outside rewardkit to build the judge
bundle.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from itertools import chain
from pathlib import Path

TESTS_DIR = Path("/tests")
TRAJECTORY_PATH = Path("/logs/agent/trajectory.json")
SCAFFOLD_SHA_PATH = Path("/opt/eval/scaffold.sha")
BUNDLE_PATH = Path("/logs/verifier/judge-bundle.md")
# RewardKit passes the judge prompt as one `claude -p` argument, and Linux caps
# a single argument at 128 KiB. A larger bundle stays on disk for the judge to read.
INLINE_BUNDLE_LIMIT = 100_000

COMMAND_TOOL_RE = re.compile(
    r"\b(command_execution|exec_command|bash|shell|terminal|run_command|write_stdin)\b",
    re.IGNORECASE,
)
WRITE_TOOL_RE = re.compile(
    r"^(Write|Edit|MultiEdit|NotebookEdit|apply_patch|write_file|create_file|str_replace_editor)$",
    re.IGNORECASE,
)
# Shell writes: apply_patch, tee, sed -i, or a redirect that is not stderr or
# /dev/null. `git status` is the authoritative signal; this only catches writes
# the agent reverted before the verifier ran. Quoted text is removed first, and
# `=>`, `->`, `>=`, and `>>`'s second `>` are not redirects.
WRITE_COMMAND_RE = re.compile(r"apply_patch|(?<![0-9&=<>-])>(?!=)\s*(?!/dev/null|&)\S|\btee\b|\bsed\s+-i\b")
QUOTED_RE = re.compile(r"'[^']*'|\"(?:[^\"\\]|\\.)*\"")
# Variables a verifier must not hand to agent-written code (npm scripts, the app).
CREDENTIAL_ENV_RE = re.compile(r"TOKEN|KEY|SECRET|PASSWORD|CREDENTIAL|AUTH", re.IGNORECASE)
SKILL_PATH_RE = re.compile(r"skills/([a-z][a-z0-9-]*)/SKILL\.md")
# Claude Code injects this line and the skill body as a user message once a Skill
# call resolves to a skill file. A failed call injects nothing. A bundled skill such
# as code-review has no directory under a skills/ dir, so it cannot pass for Consult's.
SKILL_BASE_DIR_RE = re.compile(r"Base directory for this skill: \S*/skills/([a-z][a-z0-9-]*)(?![\w/.-])")
# The directory names under agents/.agents/skills. The verifier runs where the
# repo is absent; test_skill_detection.py fails when this list drifts.
CONSULT_SKILLS = frozenset({
    "api", "architecture", "async-systems", "code-review", "commit", "contract-first", "database",
    "debugging", "documentation", "domain-modeling", "error-handling", "git-workflow", "issue-tracking",
    "observability", "official-source-check", "performance", "proof", "refactoring", "release", "scaffolding",
    "security", "specify", "ui-design", "workflow",
})
# `node --test` and `npm run -s test` may carry flags; `--test-name-pattern` alone is not a test run.
POST_WRITE_PROOF_RE = re.compile(
    r"\b(npm\s+test|npm\s+run\s+(-\S+\s+)*(test|typecheck|lint|check)|vitest|pytest|go\s+test|cargo\s+test|mvn\s+test"
    r"|uv\s+run\s+(pytest|ruff|pyright|python)|refcheck|validate[-_]skill[-_]anatomy)\b"
    r"|\bnode\s+(?:-\S+\s+)*--test(?![\w-])",
    re.IGNORECASE,
)
# A heredoc's body is data (a file's content or a script), not shell syntax.
HEREDOC_RE = re.compile(r"((?<!<)<<-?\s*(['\"]?)([A-Za-z_]\w*)\2[^\n]*\n)(.*?)(^\t*\3$|\Z)", re.MULTILINE | re.DOTALL)
SHELL_SEGMENT_RE = re.compile(r"[^;&|\n()]+")
# `$(...)` without nested parentheses, so a command substitution stays one word.
SUBSTITUTION_RE = re.compile(r"\$\([^()]*\)")
SUBSTITUTED_COMMAND_RE = re.compile(r"(?:\$\(|`)\s*([A-Za-z_][\w-]*)")
VARIABLE_RE = re.compile(r"\$\{?([A-Za-z_]\w*)\}?")
# A shell function's arguments: `$1`, `${2}`, `$@`.
POSITIONAL_RE = re.compile(r"\$\{?[1-9@*]")
ASSIGNMENT_RE = re.compile(r"([A-Za-z_]\w*)=(.*)", re.DOTALL)
# `sh -c '...'` or `bash -lc "..."` on quote-masked text; group 2 spans the script.
SHELL_WRAPPER_RE = re.compile(r"\b(?:ba|z|da)?sh\s+(?:-\w+\s+)*-\w*c\w*\s+(['\"])(_*)\1")
SHELL_FUNCTION_RE = re.compile(r"\b([A-Za-z_][\w-]*)\s*\(\)\s*\{.*?[;\n]\s*\}", re.DOTALL)
IN_PLACE_EDITORS = ("sed", "perl")
IN_PLACE_FLAG_RE = re.compile(r"-[A-Za-z0-9]*i|--in-place")
SCRIPT_FLAGS = ("-e", "-f", "--expression", "--file")
COPIERS = ("cp", "mv")
GIT_APPLY_DRY_RUN = ("--check", "--stat", "--numstat", "--summary")
INTERPRETERS = ("python", "python3", "node", "perl", "ruby")
# File-writing calls in an inline Python, Node, or Ruby script, with the target when it is a string or a name.
SCRIPT_WRITE_RE = re.compile(
    r"\bopen\(\s*(?P<open>'[^']*'|\"[^\"]*\"|[A-Za-z_]\w*)?[^)]*['\"][wax]b?\+?['\"]"
    r"|(?:\bPath\(\s*(?P<path>'[^']*'|\"[^\"]*\")\s*\))?\.write_(?:text|bytes)\("
    r"|\b(?:writeFileSync|writeFile|appendFileSync|File\.write)\(\s*(?P<call>'[^']*'|\"[^\"]*\"|[A-Za-z_]\w*)?"
)
COMMAND_FIELDS = ("cmd", "command", "script", "input", "chars")
PATH_FIELDS = ("file_path", "path", "notebook_path")
PATCH_HEADER_RE = re.compile(r"^\*\*\* (?:Add|Update|Delete) File: (.+)$|^\*\*\* Move to: (.+)$", re.MULTILINE)
REDIRECT_TARGET_RE = re.compile(r"(?<![0-9&=<>-])>>?(?!=)\s*([^\s&|;<>()]+)|\btee\s+(?:-a\s+)?([^\s&|;<>()]+)")
EXIT_CODE_RE = re.compile(r"\[exit_code\]\s*(-?\d+)|Process exited with code (-?\d+)|Exit code:? (-?\d+)")
TEST_PATH_RE = re.compile(r"(^|/)(test|tests|__tests__)/|\.(test|spec)\.[cm]?[jt]sx?$")


@dataclass
class ToolCall:
    step_index: int
    name: str
    arguments: dict
    results: list[str] = field(default_factory=list)
    seq: int = 0
    result_extras: list[dict] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)


@dataclass
class Trajectory:
    steps: list[dict]
    calls: list[ToolCall]

    @property
    def agent_messages(self) -> list[str]:
        return [str(s.get("message") or "") for s in self.steps if s.get("source") == "agent"]

    @property
    def last_user_step(self) -> int:
        """Index of the last user step: the approval boundary in a multi-step task, else the prompt."""
        indexes = [i for i, s in enumerate(self.steps) if s.get("source") == "user"]
        return indexes[-1] if indexes else -1


def load_task_meta() -> dict:
    return json.loads((TESTS_DIR / "consult.json").read_text())


def load_trajectory(path: Path = TRAJECTORY_PATH) -> Trajectory:
    if not path.exists():
        return Trajectory(steps=[], calls=[])
    data = json.loads(path.read_text())
    steps = data.get("steps") or []
    calls: list[ToolCall] = []
    for index, step in enumerate(steps):
        calls.extend(_step_calls(index, step))
    for seq, call in enumerate(calls):
        call.seq = seq
    return Trajectory(steps=steps, calls=calls)


def _step_calls(index: int, step: dict) -> list[ToolCall]:
    results_by_id: dict[str, list[str]] = {}
    extras_by_id: dict[str, list[dict]] = {}
    observation = step.get("observation") or {}
    for result in observation.get("results") or []:
        content = result.get("content")
        text = content if isinstance(content, str) else json.dumps(content)
        call_id = str(result.get("source_call_id"))
        results_by_id.setdefault(call_id, []).append(text)
        extras_by_id.setdefault(call_id, []).append(result.get("extra") or {})
    tool_calls = step.get("tool_calls") or []
    calls = []
    for call in tool_calls:
        call_id = str(call.get("tool_call_id"))
        args = call.get("arguments")
        calls.append(
            ToolCall(
                step_index=index,
                name=str(call.get("function_name") or ""),
                arguments=args if isinstance(args, dict) else {"input": args},
                results=results_by_id.get(call_id, []),
                result_extras=extras_by_id.get(call_id, []),
                metadata=_codex_call_metadata(step.get("extra") or {}, call_id, len(tool_calls)),
            )
        )
    return calls


def _codex_call_metadata(extra: dict, call_id: str, call_count: int) -> dict:
    """Codex keeps tool metadata (exit_code) on the step, per call when a step bundles several."""
    details = extra.get("tool_call_details") or {}
    if call_id in details:
        return (details[call_id] or {}).get("metadata") or {}
    if call_count == 1:
        return extra.get("tool_metadata") or {}
    return {}


def is_command_call(call: ToolCall) -> bool:
    return bool(COMMAND_TOOL_RE.search(call.name))


def command_text(call: ToolCall) -> str:
    parts = [call.arguments.get(f) for f in COMMAND_FIELDS]
    return " ".join(p for p in parts if isinstance(p, str))


def shell_text(call: ToolCall) -> str:
    """Command text with quoted strings removed, so `node -e "a => b"` is not a redirect."""
    return QUOTED_RE.sub("''", command_text(call))


def is_write_call(call: ToolCall) -> bool:
    if WRITE_TOOL_RE.match(call.name):
        return True
    return is_command_call(call) and bool(WRITE_COMMAND_RE.search(shell_text(call)))


def command_failed(call: ToolCall) -> bool:
    """A command that exited non-zero, in Claude Code or Codex trajectory form."""
    if not is_command_call(call):
        return False
    if any(extra.get("tool_result_is_error") for extra in call.result_extras):
        return True
    exit_code = call.metadata.get("exit_code")
    if isinstance(exit_code, int):
        return exit_code != 0
    return any(reported_exit_code(text) not in (None, 0) for text in call.results)


def reported_exit_code(text: str) -> int | None:
    match = EXIT_CODE_RE.search(text)
    if not match:
        return None
    return int(match.group(1) or match.group(2) or match.group(3))


def normalize_path(path: str) -> str:
    path = path.strip().strip("'\"")
    for prefix in ("/app/", "./"):
        if path.startswith(prefix):
            path = path[len(prefix):]
    return path


def written_paths(call: ToolCall) -> list[str]:
    """Repo-relative paths a write call touched: tool path args, apply_patch headers, shell redirects."""
    if WRITE_TOOL_RE.match(call.name) and call.name.lower() != "apply_patch":
        return [normalize_path(v) for f in PATH_FIELDS if isinstance(v := call.arguments.get(f), str)]
    text = command_text(call)
    if call.name.lower() == "apply_patch" or "*** Begin Patch" in text:
        return [normalize_path(a or b) for a, b in PATCH_HEADER_RE.findall(text)]
    if not is_write_call(call):
        return []
    targets = [normalize_path(a or b) for a, b in REDIRECT_TARGET_RE.findall(shell_text(call))]
    return [t for t in targets if t and not t.startswith(("/dev/", "&"))]


def first_seq(trajectory: Trajectory, predicate) -> int | None:
    """Sequence number of the first tool call matching predicate, or None."""
    return next((c.seq for c in trajectory.calls if predicate(c)), None)


def read_skill_names(trajectory: Trajectory) -> list[str]:
    """Consult skills whose body reached the agent.

    Claude Code: the skill directory in the body it injects after a Skill call,
    not the call's arguments. Codex and direct reads: a SKILL.md path in a call's
    arguments. Tool results are not read: a file listing or grep output that
    shows a SKILL.md path is not a load.
    """
    injected = chain.from_iterable(_injected_skill_names(step) for step in trajectory.steps)
    read = chain.from_iterable(SKILL_PATH_RE.findall(json.dumps(call.arguments)) for call in trajectory.calls)
    return sorted(set(chain(injected, read)) & CONSULT_SKILLS)


def _injected_skill_names(step: dict) -> list[str]:
    if step.get("source") != "user":
        return []
    message = step.get("message")
    return SKILL_BASE_DIR_RE.findall(message if isinstance(message, str) else json.dumps(message))


def question_message_count(trajectory: Trajectory) -> int:
    """Agent messages that end on a question, after the last user step.

    In a multi-step task the questions before the approval turn are the ones the
    task wants, so only messages after it count.
    """
    boundary = trajectory.last_user_step
    messages = [
        str(s.get("message") or "")
        for i, s in enumerate(trajectory.steps)
        if i > boundary and s.get("source") == "agent"
    ]
    return len([m for m in messages if ends_with_question(m)])


def ends_with_question(message: str) -> bool:
    lines = [line.strip() for line in message.strip().splitlines() if line.strip()]
    return bool(lines) and lines[-1].endswith("?")


def has_post_write_proof(trajectory: Trajectory, visible_test_cmd: str | None = None) -> bool:
    """A test run after the last workspace edit: in a later call, or later in the same command.

    Points are (call seq, offset in the command). A mutation run (mutate, test,
    restore) proves itself: its test run follows its edits, and a cp or mv in a
    command that runs tests is taken as the restore. The cost:
    `npm test && cp /tmp/fix.js src/` counts as tested.
    """
    tests = _proof_command_re(visible_test_cmd)
    edits = list(chain.from_iterable(_edit_points(c, tests) for c in trajectory.calls))
    if not edits:
        return False
    last_edit = max(edits)
    return any(point >= last_edit for point in chain.from_iterable(_test_points(c, tests) for c in trajectory.calls))


def _proof_command_re(visible_test_cmd: str | None) -> re.Pattern:
    if not visible_test_cmd:
        return POST_WRITE_PROOF_RE
    words = r"\s+".join(map(re.escape, visible_test_cmd.split()))
    return re.compile(rf"{POST_WRITE_PROOF_RE.pattern}|(?<![\w-]){words}(?![\w-])", re.IGNORECASE)


def _test_points(call: ToolCall, tests: re.Pattern) -> list[tuple[int, int]]:
    if not is_command_call(call):
        return []
    return [(call.seq, offset) for offset in _test_offsets(_shell_source(command_text(call)), tests)]


def _edit_points(call: ToolCall, tests: re.Pattern) -> list[tuple[int, int]]:
    text = command_text(call)
    if WRITE_TOOL_RE.match(call.name) or "*** Begin Patch" in text:
        return [(call.seq, 0)] if any(_in_workspace(p, True) for p in written_paths(call)) else []
    if not is_command_call(call):
        return []
    raw = _shell_source(text)
    offsets = _shell_edit_offsets(text, raw, count_copies=not _test_offsets(raw, tests))
    return [(call.seq, offset) for offset in offsets]


def _shell_source(text: str) -> str:
    """Command text with heredoc bodies blanked and `\\`-newline continuations joined, keeping offsets."""
    return _blank_heredoc_bodies(text).replace("\\\n", "  ")


def _test_offsets(raw: str, tests: re.Pattern) -> list[int]:
    """Offsets of test runs outside quotes, so `grep 'node --test'` is not a run.

    A run in a `sh -c` or `bash -lc` script counts where the wrapper starts. A
    run in a shell function counts where the function is called.
    """
    mask = _mask_quotes(raw)
    functions = [m for m in SHELL_FUNCTION_RE.finditer(mask) if tests.search(m[0])]
    direct = [m.start() for m in tests.finditer(mask) if not _in_function(m.start(), functions)]
    wrappers = SHELL_WRAPPER_RE.finditer(mask)
    wrapped = [m.start() for m in wrappers if tests.search(_mask_quotes(raw[m.start(2):m.end(2)]))]
    return direct + wrapped + _function_calls(raw, mask, functions)


def _function_calls(raw: str, mask: str, functions: list[re.Match]) -> list[int]:
    """Offsets where one of the functions is called outside its definition: as a
    command, or in a `$(...)` or backtick substitution, which runs inside double quotes too.
    """
    names = {m[1] for m in functions}
    commands = [s.start() for s in SHELL_SEGMENT_RE.finditer(mask) if (s[0].split() or [""])[0] in names]
    substitutions = [m.start() for m in SUBSTITUTED_COMMAND_RE.finditer(raw) if m[1] in names]
    return [offset for offset in commands + substitutions if not _in_function(offset, functions)]


def _in_function(offset: int, functions: list[re.Match]) -> bool:
    return any(m.start() <= offset < m.end() for m in functions)


def _shell_edit_offsets(text: str, raw: str, count_copies: bool) -> list[int]:
    """Offsets of segments with a shell write that resolves inside /app: a
    redirect, tee, sed -i or perl -i operand, or an inline interpreter script
    that writes a file. With `count_copies`, also a cp or mv destination or a
    git apply. git checkout and git stash are not writes.

    A call starts in /app: Claude Code resets its shell there. After a `cd` to
    a path outside /app, a variable, or ~, relative targets are outside until a
    `cd` back into /app. Subshell scope is not tracked. A variable the command
    sets (`f=...`, `for f in ...`) resolves to its values. A function argument
    ($1) or a command substitution that does not run mktemp resolves as the
    current directory. Any other variable ($TMPDIR) is outside.
    """
    mask = SUBSTITUTION_RE.sub(lambda m: "$" + "_" * (len(m[0]) - 1), _mask_quotes(raw))
    in_workspace, variables, offsets = True, {}, []
    for segment in SHELL_SEGMENT_RE.finditer(mask):
        words = _shell_words(raw, segment)
        if words[:1] == ["cd"]:
            in_workspace = _cd_in_workspace(words[1:], in_workspace)
        variables = {**variables, **_assignments(words)}
        targets = _expand(_segment_targets(text, raw, segment, words, count_copies), variables)
        if any(_in_workspace(target, in_workspace) for target in targets):
            offsets.append(segment.start())
    return offsets


def _blank_heredoc_bodies(text: str) -> str:
    """Replace heredoc bodies with spaces, keeping offsets and line breaks."""
    return HEREDOC_RE.sub(lambda m: m[1] + re.sub(r"[^\n]", " ", m[4]) + m[5], text)


def _mask_quotes(text: str) -> str:
    """Replace quoted text with underscores, keeping the quotes and offsets, so quoted `>` or `;` is not syntax."""
    return QUOTED_RE.sub(lambda m: m[0][0] + "_" * (len(m[0]) - 2) + m[0][-1], text)


def _shell_words(raw: str, segment: re.Match) -> list[str]:
    """A segment's words, split on the quote-masked text and read from the raw text."""
    base = segment.start()
    return [raw[base + w.start():base + w.end()] for w in re.finditer(r"\S+", segment[0])]


def _segment_targets(text: str, raw: str, segment: re.Match, words: list[str], count_copies: bool) -> list[str]:
    copies = _copy_targets(words) if count_copies else []
    return _redirect_targets(raw, segment) + _in_place_targets(words) + _script_writes(text, segment, words) + copies


def _redirect_targets(raw: str, segment: re.Match) -> list[str]:
    base = segment.start()
    matches = REDIRECT_TARGET_RE.finditer(segment[0])
    return [raw[base + m.start(m.lastindex):base + m.end(m.lastindex)] for m in matches]


def _in_place_targets(words: list[str]) -> list[str]:
    """File operands of `sed -i` or `perl -pi`: the words after the script that are not options.

    With no file operand the files come from xargs, so the target is the current directory.
    """
    editor = next((word for word in words if word in IN_PLACE_EDITORS), None)
    args = words[words.index(editor) + 1:] if editor else []
    if not any(IN_PLACE_FLAG_RE.match(word) for word in args):
        return []
    operands, has_script_flag, skip_next = [], False, False
    for word in args:
        if skip_next:
            skip_next = False
        elif word in SCRIPT_FLAGS:
            has_script_flag = skip_next = True
        elif not word.startswith("-"):
            operands.append(word)
    return (operands if has_script_flag else operands[1:]) or ["."]


def _copy_targets(words: list[str]) -> list[str]:
    """The destination of cp or mv, or the working tree for git apply."""
    if words[:1] and words[0] in COPIERS:
        return [word for word in words[1:] if not word.startswith("-")][-1:]
    if words[:2] == ["git", "apply"] and not set(words) & set(GIT_APPLY_DRY_RUN):
        return ["."]
    return []


def _script_writes(text: str, segment: re.Match, words: list[str]) -> list[str]:
    """Files an interpreter's inline script (-c, -e, or a heredoc) writes."""
    if not words or words[0] not in INTERPRETERS:
        return []
    bodies = [m[4] for m in HEREDOC_RE.finditer(text) if segment.start() <= m.start() < segment.end()]
    script = "\n".join([text[segment.start():segment.end()], *bodies])
    return [_script_target(script, m["open"] or m["path"] or m["call"]) for m in SCRIPT_WRITE_RE.finditer(script)]


def _script_target(script: str, target: str | None) -> str:
    """A string literal, the literal a name is first assigned in the script, or else the current directory."""
    if not target or target[0] in "'\"":
        return target or "."
    assigned = re.search(rf"\b{target}\s*=\s*('[^']*'|\"[^\"]*\")", script)
    return assigned[1] if assigned else "."


def _assignments(words: list[str]) -> dict[str, list[str]]:
    """Variables a segment sets: a `for` loop's list, `read` names, or `name=value` words.

    A `read` name comes from stdin, so it resolves as the current directory.
    """
    if len(words) > 2 and words[0] == "for" and words[2] == "in":
        return {words[1]: [word.strip("'\"") for word in words[3:]]}
    if "read" in words:
        return {word: ["."] for word in words[words.index("read") + 1:] if not word.startswith("-")}
    return {m[1]: [m[2].strip("'\"")] for m in map(ASSIGNMENT_RE.fullmatch, words) if m}


def _expand(targets: list[str], variables: dict[str, list[str]]) -> list[str]:
    return list(chain.from_iterable(_expand_target(target.strip("'\""), variables) for target in targets))


def _expand_target(target: str, variables: dict[str, list[str]]) -> list[str]:
    """The target with its first variable the command set replaced by each of its values."""
    match = next((m for m in VARIABLE_RE.finditer(target) if m[1] in variables), None)
    if match is None:
        return [target]
    return [target[:match.start()] + value + target[match.end():] for value in variables[match[1]]]


def _cd_in_workspace(args: list[str], current: bool) -> bool:
    target = args[0].strip("'\"") if args else "~"
    if target.startswith(("/", "$", "~")):
        return target == "/app" or target.startswith("/app/")
    return current


def _in_workspace(path: str, cwd_in_workspace: bool) -> bool:
    path = path.strip("'\"")
    if path.startswith(("$(", "`")) or POSITIONAL_RE.match(path):
        return cwd_in_workspace and "mktemp" not in path
    if path.startswith(("/", "$", "~")):
        return path.startswith("/app/")
    return cwd_in_workspace and bool(path)


def git(workspace: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(workspace), *args], capture_output=True, text=True, check=False).stdout


def scaffold_sha(workspace: Path) -> str:
    """The scaffold commit the Dockerfile made; stable even if the agent commits."""
    if SCAFFOLD_SHA_PATH.exists():
        return SCAFFOLD_SHA_PATH.read_text().strip()
    return (git(workspace, "rev-list", "--max-parents=0", "HEAD").split() or ["HEAD"])[0]


def changed_paths(workspace: Path) -> list[str]:
    """Paths changed since the scaffold commit: tracked edits (committed or not) plus untracked files."""
    tracked = git(workspace, "diff", "--name-only", scaffold_sha(workspace)).split("\n")
    untracked = git(workspace, "ls-files", "--others", "--exclude-standard").split("\n")
    return sorted({p.strip().strip('"') for p in tracked + untracked if p.strip()})


def classify(path: str) -> str:
    if TEST_PATH_RE.search(path):
        return "test"
    if path.endswith(".md"):
        return "documentation"
    if "package.json" in path:
        return "config"
    return "source"


def run_command(workspace: Path, argv: list[str], timeout: int) -> tuple[bool, str]:
    """Run agent-influenced code (tests, npm scripts, the app) without the verifier's credentials."""
    env = {k: v for k, v in os.environ.items() if not CREDENTIAL_ENV_RE.search(k)}
    try:
        result = subprocess.run(argv, cwd=workspace, env=env, capture_output=True, text=True, timeout=timeout, check=False)
    except subprocess.TimeoutExpired:
        return False, f"timed out after {timeout}s: {' '.join(argv)}"
    return result.returncode == 0, (result.stdout + result.stderr)[-4000:]


def visible_tests_pass(workspace: Path, meta: dict) -> bool:
    cmd = meta.get("visible_test_cmd")
    if not cmd:
        return False
    ok, _ = run_command(workspace, ["bash", "-lc", cmd], timeout=120)
    return ok


def hidden_check_passes(workspace: Path) -> bool:
    script = TESTS_DIR / "hidden.mjs"
    if not script.exists():
        return False
    ok, output = run_command(workspace, ["node", "--input-type=module", "-e", script.read_text()], timeout=60)
    if not ok:
        sys.stderr.write(f"consult: hidden check failed:\n{output[-1500:]}\n")
    return ok


def final_agent_message(trajectory: Trajectory) -> str:
    messages = [m for m in trajectory.agent_messages if m.strip()]
    return messages[-1] if messages else ""


def build_bundle(workspace: Path) -> str:
    """Judge input: the diff against the committed scaffold plus new files and the final message."""
    diff = git(workspace, "diff", scaffold_sha(workspace))
    untracked = git(workspace, "ls-files", "--others", "--exclude-standard").split()
    sections = ["# Changes against the starting repository", "", "## Diff", "", "```diff", diff.strip(), "```", ""]
    for rel in untracked:
        file_path = workspace / rel
        if not file_path.is_file() or file_path.stat().st_size > 64_000:
            continue
        sections += [f"## New file: {rel}", "", "```", file_path.read_text(errors="replace"), "```", ""]
    final = final_agent_message(load_trajectory())
    sections += ["## Final agent message", "", final or "No final message was captured.", ""]
    return "\n".join(sections)


def judge_credentials_present() -> bool:
    import os

    judge = os.environ.get("REWARDKIT_JUDGE", "claude-code")
    if judge.startswith("anthropic/") or judge.lower().startswith("claude"):
        return bool(os.environ.get("CLAUDE_CODE_OAUTH_TOKEN") or os.environ.get("ANTHROPIC_API_KEY"))
    if judge.startswith("openai/") or judge.startswith("gpt"):
        return bool(os.environ.get("OPENAI_API_KEY"))
    return True


def prepare_tests(tests_dir: Path) -> None:
    """Adjust the uploaded tests dir to what this trial can actually score.

    Without judge credentials, or with CONSULT_EVAL_SKIP_JUDGE set, the judge
    dimension is removed and its weight dropped from reward.toml so the
    programmatic dimensions still produce a reward. Otherwise the claude-code
    judge gets its inputs inline, so it scores in one turn instead of reading
    files with tool calls.
    """
    import os
    import shutil

    judge_dir = tests_dir / "judge"
    if not judge_dir.exists():
        return
    skip = bool(os.environ.get("CONSULT_EVAL_SKIP_JUDGE")) or not judge_credentials_present()
    if skip:
        shutil.rmtree(judge_dir)
        reward = tests_dir / "reward.toml"
        reward.write_text(re.sub(r",\s*judge\s*=\s*[0-9.]+", "", reward.read_text()))
        sys.stderr.write("consult: judge skipped (no credentials or CONSULT_EVAL_SKIP_JUDGE); reward excludes judge\n")
        return
    if os.environ.get("REWARDKIT_JUDGE", "claude-code") != "claude-code":
        return
    if BUNDLE_PATH.exists() and BUNDLE_PATH.stat().st_size > INLINE_BUNDLE_LIMIT:
        sys.stderr.write("consult: judge bundle over the inline limit; the judge reads it from disk\n")
        return
    inline_judge_inputs(judge_dir, BUNDLE_PATH)


def inline_judge_inputs(judge_dir: Path, bundle_path: Path) -> None:
    """Append the task instruction and the bundle to the judge prompt template."""
    prompt = judge_dir / "prompt.md"
    instruction = (judge_dir / "instruction.md").read_text()
    bundle = bundle_path.read_text() if bundle_path.exists() else "No bundle was built."
    sections = [prompt.read_text().rstrip(), "", "# Task instruction", "", instruction.strip(), "", bundle.strip(), ""]
    prompt.write_text("\n".join(sections))


def main(argv: list[str]) -> int:
    if argv[1:2] == ["bundle"]:
        sys.stdout.write(build_bundle(Path(argv[2] if len(argv) > 2 else "/app")))
        return 0
    if argv[1:2] == ["prepare"]:
        prepare_tests(Path(argv[2]) if len(argv) > 2 else TESTS_DIR)
        return 0
    sys.stderr.write("usage: consult_lib.py bundle [workspace] | prepare [tests_dir]\n")
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
