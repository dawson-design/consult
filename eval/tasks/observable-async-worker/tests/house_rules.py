"""Checks for the house defaults, simplicity, and staged tasks (the houseStyle suite).

Synced from eval/verifier/shared/house_rules.py into every code task's tests/ by
eval/scripts/sync_tests.py. Do not edit the copy under tests/.

consult_rules.score() looks rule ids up here after its own CHECKS. Each check is
(workspace, trajectory, meta) -> float in [0, 1], like those in consult_rules.

Static checks read facts that code_shape.mjs extracts with the TypeScript
compiler API. Shape scores are fractions of functions, decision points, or
files, so a larger change is never penalized for its size, only for how it is
built: long or deeply nested functions, unnamed compound conditions, logic
mixed with effects, shared mutable state, import cycles, or single-use
abstractions.

Staged tasks split the trajectory into stages at user turns that start with a
heading in consult.json `stage_headings`, and into turns at those headings and
at approvals. Step verifiers snapshot the workspace into /opt/eval/snapshots/<n>
after step n (0-based), so `core.simple.s<k>` scores the tree as stage k left it.
"""

from __future__ import annotations

import functools
import json
import os
import re
import statistics
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import consult_lib as cl
import consult_rules as cr

ANALYZER = Path(__file__).resolve().parent / "code_shape.mjs"
SNAPSHOTS_DIR = Path("/opt/eval/snapshots")
SOURCE_SUFFIXES = (".ts", ".tsx", ".mts", ".cts", ".js", ".jsx", ".mjs", ".cjs")
SKIP_PARTS = {"node_modules", ".git", "dist", "build", "coverage"}

# core rule 4: functions of about 25-30 lines, nesting under three levels.
MAX_FUNCTION_LINES = 30
MAX_NESTING = 2

# default 2: a top-level folder or file named for a technical role, not a domain feature.
LAYER_NAMES = frozenset(
    [
        "controller",
        "controllers",
        "service",
        "services",
        "model",
        "models",
        "entity",
        "entities",
        "dto",
        "dtos",
        "type",
        "types",
        "interface",
        "interfaces",
        "validator",
        "validators",
        "validation",
        "schema",
        "schemas",
        "util",
        "utils",
        "helper",
        "helpers",
        "error",
        "errors",
        "constant",
        "constants",
        "repository",
        "repositories",
        "repo",
        "repos",
        "dao",
        "middleware",
        "middlewares",
        "manager",
        "managers",
        "handler",
        "handlers",
    ]
)
SOURCE_ROOTS = ("src", "lib", "app")
TEST_DIR_NAMES = {"__tests__", "test", "tests"}
# default 9: jitter beside the outbound call.
OUTBOUND_RE = re.compile(r"\bfetch\s*\(|from\s+['\"](undici|axios|got|ky|node-fetch)['\"]")
JITTER_RE = re.compile(r"Math\.random|jitter|randomi[sz]e", re.IGNORECASE)
APPROVAL_RE = re.compile(r"^Approved\b")
EDIT_TOOLS = ("Edit", "MultiEdit")
REVERT_COMMAND_RE = re.compile(r"\bgit\s+(checkout|restore|stash)\b|\bsed\s+-i\b|\bmv\s+\S+\.(bak|orig)\b")
# default 7: a write that states a contract: a spec, schema, or types file, or a write of only declarations.
CONTRACT_PATH_RE = re.compile(
    r"(^|/)openapi\.(ya?ml|json)$|(^|/)(contracts?|schemas?|types)(/|\.[cm]?[jt]s$)|\.(schema|types|contract)\.[cm]?[jt]s$|\.d\.ts$|(^|/)docs/api"
)
DECLARATION_RE = re.compile(r"\b(type|interface)\s+\w+|\bz\.(object|discriminatedUnion|union|enum|literal)\(")
IMPLEMENTATION_RE = re.compile(r"\bfunction\s+\w*\s*\(|=>\s*\{|\bclass\s+\w+")
# human 7: the report's sections, in order.
REPORT_SECTIONS = (
    re.compile(r"attention|decid|decision|need(s)? (you|your)|review first|heads.up|action", re.IGNORECASE),
    re.compile(r"what changed|changes|changed|built|summary", re.IGNORECASE),
    re.compile(r"how it works|data enters|read first|entry point|key decision|walkthrough|flow", re.IGNORECASE),
    re.compile(r"prove|proof|verif|tests?|checks?", re.IGNORECASE),
    re.compile(
        r"unproven|not (yet )?(tested|proven|verified|covered)|untested|gaps?|limitations?|caveats?|risks?",
        re.IGNORECASE,
    ),
)
HEADING_RE = re.compile(r"^\s*(#{1,6}\s+.+|\*\*[^*]+\*\*:?\s*$|[A-Z][^.!?\n]{0,60}:\s*$)", re.MULTILINE)


# Static facts from code_shape.mjs.


def is_analyzable(rel: str) -> bool:
    """Non-test, non-config, non-declaration source outside generated and vendored folders."""
    parts = rel.split("/")
    return (
        rel.endswith(SOURCE_SUFFIXES)
        and not rel.endswith(".d.ts")
        and not SKIP_PARTS.intersection(parts)
        and cl.classify(rel) != "test"
        and not cr.CONFIG_CODE_RE.search(rel)
    )


def source_files(root: Path) -> tuple[str, ...]:
    """Every analyzable source file under root, relative and sorted."""
    found = (str(p.relative_to(root)) for p in root.rglob("*") if p.is_file() and not SKIP_PARTS.intersection(p.parts))
    return tuple(sorted(rel for rel in found if is_analyzable(rel)))


def scoped_files(workspace: Path, meta: dict) -> tuple[str, ...]:
    """The files a task scores: every source file, or only changed ones when consult.json says `shape_scope: changed`."""
    if meta.get("shape_scope") == "changed":
        changed = (p for p in cl.changed_paths(workspace) if (workspace / p).is_file())
        return tuple(sorted(p for p in changed if is_analyzable(p)))
    return source_files(workspace)


@functools.cache
def shape(root: Path, files: tuple[str, ...]) -> dict:
    """Facts for the files; RuntimeError when the analyzer fails, which score() turns into 0."""
    if not files:
        return {}
    env = {
        "PATH": os.environ.get("PATH", ""),
        "CONSULT_ANALYZER_DIR": os.environ.get("CONSULT_ANALYZER_DIR", "/opt/eval/analyzer"),
    }
    result = subprocess.run(
        ["node", str(ANALYZER), str(root), *files], capture_output=True, text=True, timeout=300, env=env, check=False
    )
    if result.returncode != 0:
        raise RuntimeError(f"code_shape.mjs failed: {result.stderr[-2000:]}")
    return json.loads(result.stdout)


def built_beyond_scaffold(root: Path, files: tuple[str, ...], workspace: Path) -> bool:
    """More source files than the scaffold had: an empty tree would score a vacuous 1.0."""
    scaffold = cl.git(workspace, "ls-tree", "-r", "--name-only", cl.scaffold_sha(workspace)).split()
    return len(files) > len([p for p in scaffold if is_analyzable(p)])


# Shape scores: each a fraction in [0, 1].


def is_readable(function: dict) -> bool:
    """core rule 4: short, shallow, and every compound condition named."""
    return function["lines"] <= MAX_FUNCTION_LINES and function["nesting"] <= MAX_NESTING and function["compound"] == 0


def function_shape(facts: dict) -> float:
    """Share of block-bodied functions that are readable in one pass."""
    functions = [f for f in facts.get("functions", []) if f["block"]]
    return statistics.fmean(1.0 if is_readable(f) else 0.0 for f in functions) if functions else 1.0


def logic_purity(facts: dict) -> float:
    """core rule 1: share of business-logic decisions in pure functions, away from I/O and mutation.

    Logic decisions are conditions with a real check, loops, and switch cases;
    null checks and Result plumbing (`if (!r.ok) return ...`) are wiring, not logic.
    """
    functions = facts.get("functions", [])
    total = sum(f["logic"] for f in functions)
    pure = sum(f["logic"] for f in functions if f["pure"])
    return pure / total if total else 1.0


def is_stateful_class(cls: dict) -> bool:
    """A class that bundles behavior with mutable state (house default 1)."""
    return cls["methods"] > 0 and (cls["mutableFields"] > 0 or cls["thisMutation"])


def state_isolation(facts: dict) -> float:
    """Share of files with no module-level state that functions mutate and no stateful class."""
    files = set(facts.get("imports", {}))
    stateful = {s["file"] for s in facts.get("sharedMutable", [])}
    stateful |= {c["file"] for c in facts.get("classes", []) if is_stateful_class(c)}
    return 1.0 - len(stateful & files) / len(files) if files else 1.0


def acyclic_imports(facts: dict) -> float:
    """1.0 when no import cycle joins the scored files."""
    graph = facts.get("imports", {})
    done: set[str] = set()

    def cycles_from(node: str, path: tuple[str, ...]) -> bool:
        if node in path:
            return True
        if node in done:
            return False
        found = any(cycles_from(n, (*path, node)) for n in graph.get(node, []))
        done.add(node)
        return found

    return 0.0 if any(cycles_from(n, ()) for n in graph) else 1.0


def no_speculative_abstraction(facts: dict) -> float:
    """core rule 2: no interface with exactly one implementation and no abstract class."""
    single = [name for name, count in facts.get("interfaces", {}).items() if count == 1]
    return 0.0 if single or facts.get("abstractClasses", 0) else 1.0


def simplicity(facts: dict) -> float:
    """The iron law, measured: the mean of the five shape scores."""
    parts = (function_shape, logic_purity, state_isolation, acyclic_imports, no_speculative_abstraction)
    return statistics.fmean(part(facts) for part in parts)


# Checks over the final workspace.


def final_facts(workspace: Path, meta: dict) -> dict | None:
    """The scored files' facts, or None when nothing was built beyond the scaffold."""
    files = scoped_files(workspace, meta)
    if not files or (meta.get("shape_scope") != "changed" and not built_beyond_scaffold(workspace, files, workspace)):
        return None
    return shape(workspace, files)


def shape_check(score):
    """A check that applies a facts score to the final workspace; nothing built scores 0."""

    def check(workspace: Path, trajectory: cl.Trajectory, meta: dict) -> float:
        facts = final_facts(workspace, meta)
        return 0.0 if facts is None else score(facts)

    check.__doc__ = score.__doc__
    return check


def stage_simplicity(stage: int):
    """core.simple.s<stage>: simplicity of the tree as the stage's last step left it."""

    def check(workspace: Path, trajectory: cl.Trajectory, meta: dict) -> float:
        per_stage = int(meta.get("steps_per_stage", 3))
        root = stage_root(stage, per_stage, int(meta.get("stages", 5)), workspace)
        if root is None:
            return 0.0
        files = source_files(root)
        if not files or not built_beyond_scaffold(root, files, workspace):
            return 0.0
        return simplicity(shape(root, files))

    return check


def stage_root(stage: int, per_stage: int, stages: int, workspace: Path) -> Path | None:
    """The final stage is the workspace itself; earlier stages are their last step's snapshot."""
    if stage == stages:
        return workspace
    snapshot = SNAPSHOTS_DIR / str(stage * per_stage - 1)
    return snapshot if snapshot.is_dir() else None


def default_1(facts: dict) -> float:
    """Functional core: no class that bundles behavior with mutable state, no inheritance but from Error."""
    classes = facts.get("classes", [])
    inherits = [c for c in classes if c["extends"] and not c["isError"]]
    return 0.0 if inherits or any(is_stateful_class(c) for c in classes) else 1.0


def is_layered(rel: str) -> bool:
    """The file's top folder under src/ (or the file itself, at that level) is named for a technical role."""
    parts = rel.split("/")
    if parts[0] in SOURCE_ROOTS and len(parts) > 1:
        parts = parts[1:]
    head = parts[0] if len(parts) > 1 else parts[0].split(".")[0]
    return head.lower() in LAYER_NAMES


def is_colocated(rel: str, workspace: Path) -> bool:
    """A test file sits beside source it covers: its folder (or a __tests__ folder's parent) holds source."""
    folder = Path(rel).parent
    if folder.name == "__tests__":
        folder = folder.parent
    if TEST_DIR_NAMES.intersection(folder.parts):
        return False
    directory = workspace / folder
    return directory.is_dir() and any(is_analyzable(str(p.relative_to(workspace))) for p in directory.iterdir())


def default_2(workspace: Path, trajectory: cl.Trajectory, meta: dict) -> float:
    """Feature folders: new source is not filed by technical role, and new tests sit beside their code."""
    changed = [p for p in cl.changed_paths(workspace) if (workspace / p).is_file()]
    sources = [p for p in changed if is_analyzable(p)]
    tests = [p for p in changed if cl.classify(p) == "test" and p.endswith(SOURCE_SUFFIXES)]
    if not sources:
        return 0.0
    parts = [statistics.fmean(0.0 if is_layered(p) else 1.0 for p in sources)]
    if tests:
        parts.append(statistics.fmean(1.0 if is_colocated(p, workspace) else 0.0 for p in tests))
    return statistics.fmean(parts)


def default_4(facts: dict) -> float:
    """Result-style values for expected failures: 1 with none thrown, 0.5 when some still throw, 0 without Results."""
    result_style = facts.get("resultLibrary") or any(u["result"] for u in facts.get("unions", []))
    if not result_style:
        return 0.0
    return 0.5 if any(t["expected"] for t in facts.get("throws", [])) else 1.0


def package_dependencies(workspace: Path) -> set[str]:
    path = workspace / "package.json"
    try:
        manifest = json.loads(path.read_text()) if path.is_file() else {}
    except json.JSONDecodeError:
        return set()
    return set(manifest.get("dependencies") or {}) | set(manifest.get("devDependencies") or {})


def default_5(workspace: Path, trajectory: cl.Trajectory, meta: dict) -> float:
    """Explicit state variants (a discriminated union with variant-only fields) and Zod parsing at the boundary."""
    facts = final_facts(workspace, meta)
    if facts is None:
        return 0.0
    variants = any(
        not u["result"] and u["variants"] >= 3 and u["specificVariants"] >= 2 for u in facts.get("unions", [])
    )
    zod = facts.get("zodImported") and facts.get("zodParseCalls", 0) > 0 and "zod" in package_dependencies(workspace)
    return statistics.fmean([1.0 if variants else 0.0, 1.0 if zod else 0.0])


def source_text(workspace: Path, meta: dict, suffixes: tuple[str, ...] = ()) -> str:
    files = list(scoped_files(workspace, meta))
    extra = [str(p.relative_to(workspace)) for s in suffixes for p in workspace.rglob(f"*{s}")]
    extra = [p for p in extra if not SKIP_PARTS.intersection(p.split("/"))]
    return "\n".join((workspace / p).read_text(errors="replace") for p in files + extra)


def default_9(workspace: Path, trajectory: cl.Trajectory, meta: dict) -> float:
    """Timeout, transient-only retry (probe), and jittered backoff beside the outbound call (static)."""
    files = scoped_files(workspace, meta)
    texts = [(workspace / p).read_text(errors="replace") for p in files]
    jitter = any(OUTBOUND_RE.search(t) and JITTER_RE.search(t) for t in texts)
    return 0.75 * float(cr.probe_results(workspace).get("default.9", 0)) + (0.25 if jitter else 0.0)


def probe_check(rule_id: str):
    def check(workspace: Path, trajectory: cl.Trajectory, meta: dict) -> float:
        return float(cr.probe_results(workspace).get(rule_id, 0))

    check.__doc__ = f"{rule_id} from the task's rule probe."
    return check


def core_2(workspace: Path, trajectory: cl.Trajectory, meta: dict) -> float:
    """No environment variable or command-line flag the request did not name (consult.json `allowed_env`)."""
    facts = final_facts(workspace, meta)
    if facts is None:
        return 0.0
    extra = set(facts.get("env", [])) - set(meta.get("allowed_env") or [])
    return 0.0 if extra or facts.get("argv") else 1.0


def new_files(workspace: Path) -> list[str]:
    """Files that exist now but were not in the scaffold commit."""
    scaffold = set(cl.git(workspace, "ls-tree", "-r", "--name-only", cl.scaffold_sha(workspace)).split())
    return [p for p in cl.changed_paths(workspace) if (workspace / p).is_file() and p not in scaffold]


def scaffold_dependencies(workspace: Path) -> set[str]:
    text = cl.git(workspace, "show", f"{cl.scaffold_sha(workspace)}:package.json")
    manifest = json.loads(text) if text.strip() else {}
    return set(manifest.get("dependencies") or {}) | set(manifest.get("devDependencies") or {})


def follows_errors(facts: dict, text: str, error_classes: list[str]) -> float:
    """No Result type introduced, and the change throws the project's own error classes."""
    introduced_results = facts.get("resultLibrary") or any(u["result"] for u in facts.get("unions", []))
    throws_project = any(f"new {name}(" in text for name in error_classes)
    return statistics.fmean([0.0 if introduced_results else 1.0, 1.0 if throws_project else 0.0])


def default_follow(workspace: Path, trajectory: cl.Trajectory, meta: dict) -> float:
    """House defaults yield to the project: its layer folders, classes, error classes, test folder, and dependencies."""
    project = meta.get("project") or {}
    facts = final_facts(workspace, meta)
    added = new_files(workspace)
    sources = [p for p in added if is_analyzable(p)]
    if facts is None or not sources:
        return 0.0
    layers = tuple(f"{layer}/" for layer in project.get("layers", []))
    tests = [p for p in added if cl.classify(p) == "test"]
    class_layer = f"{project.get('class_layer', '')}/"
    parts = [
        statistics.fmean(1.0 if p.startswith(layers) else 0.0 for p in sources),
        statistics.fmean(1.0 if p.startswith(f"{project.get('test_dir', 'test')}/") else 0.0 for p in tests)
        if tests
        else 0.0,
        1.0 if any(c["file"].startswith(class_layer) for c in facts.get("classes", [])) else 0.0,
        follows_errors(facts, source_text(workspace, meta), project.get("error_classes", [])),
        1.0 if package_dependencies(workspace) <= scaffold_dependencies(workspace) else 0.0,
    ]
    return statistics.fmean(parts)


# Stages and turns in the trajectory.


def stage_turns(trajectory: cl.Trajectory, meta: dict) -> list[list[tuple[int, int]]]:
    """Per stage, its turns as [start, end) step ranges. Other user steps (skill bodies, subagent prompts) are not turns."""
    headings = tuple(meta.get("stage_headings") or [])
    if not headings:
        return []
    starts = [
        (i, str(s.get("message") or "").lstrip())
        for i, s in enumerate(trajectory.steps)
        if s.get("source") == "user"
        and (
            APPROVAL_RE.match(str(s.get("message") or "").lstrip())
            or str(s.get("message") or "").lstrip().startswith(headings)
        )
    ]
    stages: list[list[tuple[int, int]]] = []
    for (start, message), end in zip(starts, [s for s, _ in starts[1:]] + [len(trajectory.steps)]):
        if message.startswith(headings) or not stages:
            stages.append([])
        stages[-1].append((start, end))
    return stages


def calls_in(trajectory: cl.Trajectory, span: tuple[int, int]) -> list[cl.ToolCall]:
    return [c for c in trajectory.calls if span[0] <= c.step_index < span[1]]


def last_message_in(trajectory: cl.Trajectory, span: tuple[int, int]) -> str:
    messages = [
        str(trajectory.steps[i].get("message") or "")
        for i in range(span[0], span[1])
        if trajectory.steps[i].get("source") == "agent" and str(trajectory.steps[i].get("message") or "").strip()
    ]
    return messages[-1] if messages else ""


def is_source_write(call: cl.ToolCall) -> bool:
    return any(is_analyzable(p) or cl.classify(p) == "test" for p in cl.written_paths(call))


def writes_source_only(call: cl.ToolCall) -> bool:
    return any(is_analyzable(p) for p in cl.written_paths(call))


def writes_test(call: cl.ToolCall) -> bool:
    return any(cl.classify(p) == "test" for p in cl.written_paths(call))


def stage_mean(trajectory: cl.Trajectory, meta: dict, score) -> float:
    """Mean of score(stage turns) over stages it applies to (score returns None to skip a stage)."""
    values = [v for v in (score(trajectory, turns) for turns in stage_turns(trajectory, meta)) if v is not None]
    return statistics.fmean(values) if values else 0.0


def human_1_stages(workspace: Path, trajectory: cl.Trajectory, meta: dict) -> float:
    """Each stage's brief turn stops at the plan: no gated write, or a build flagged provisional."""
    gated = meta.get("gated_paths") or ["*"]

    def stopped(traj: cl.Trajectory, turns: list[tuple[int, int]]) -> float:
        brief = turns[0]
        wrote = any(
            cr.matches_any(p, gated) and not cr.PLAN_DOC_RE.search(p)
            for c in calls_in(traj, brief)
            for p in cl.written_paths(c)
        )
        if not wrote:
            return 1.0
        return 1.0 if cr.PROVISIONAL_RE.search(last_message_in(traj, brief)) else 0.0

    return stage_mean(trajectory, meta, stopped)


def report_order(message: str) -> float:
    """human rule 7: share of the five sections present, halved when they are out of order."""
    headings = [m.group(0) for m in HEADING_RE.finditer(message)]
    text = "\n".join(headings) if len(headings) >= 3 else message
    positions = [m.start() if (m := section.search(text)) else None for section in REPORT_SECTIONS]
    found = [p for p in positions if p is not None]
    present = len(found) / len(REPORT_SECTIONS)
    return present if found == sorted(found) else present / 2


def human_7(workspace: Path, trajectory: cl.Trajectory, meta: dict) -> float:
    """Each stage's report (the last message of the last turn that wrote code) follows the report order."""

    def scored(traj: cl.Trajectory, turns: list[tuple[int, int]]) -> float | None:
        building = [span for span in turns if any(is_source_write(c) for c in calls_in(traj, span))]
        return report_order(last_message_in(traj, building[-1])) if building else None

    return stage_mean(trajectory, meta, scored)


def is_inverse_edit(first: cl.ToolCall, second: cl.ToolCall) -> bool:
    a, b = first.arguments, second.arguments
    return (
        first.name in EDIT_TOOLS
        and second.name in EDIT_TOOLS
        and a.get("file_path") == b.get("file_path")
        and bool(a.get("old_string"))
        and a.get("old_string") == b.get("new_string")
        and a.get("new_string") == b.get("old_string")
    )


def broke_by_hand(calls: list[cl.ToolCall]) -> bool:
    """A source edit, a failing test run, then its exact reversal or a revert command."""
    failing = [i for i, c in enumerate(calls) if cr.is_test_command(c) and cl.command_failed(c)]
    for f in failing:
        before = [
            c
            for c in calls[:f]
            if writes_source_only(c) or (cl.is_command_call(c) and REVERT_COMMAND_RE.search(cl.command_text(c)))
        ]
        after = calls[f + 1 :]
        if any(is_inverse_edit(b, a) for b in before for a in after):
            return True
        if before and any(cl.is_command_call(a) and REVERT_COMMAND_RE.search(cl.command_text(a)) for a in after):
            return True
    return False


def saw_red_first(calls: list[cl.ToolCall]) -> bool:
    """A test written, run and failing for a real reason, then source written and the tests passing."""
    for i, call in enumerate(calls):
        if not (cr.is_test_command(call) and cl.command_failed(call)):
            continue
        if cr.INCONCLUSIVE_RE.search("\n".join(call.results)):
            continue
        last_write = next((c for c in reversed(calls[:i]) if is_source_write(c)), None)
        if last_write is None or not writes_test(last_write):
            continue
        rest = calls[i + 1 :]
        fixed = next((j for j, c in enumerate(rest) if writes_source_only(c)), None)
        if fixed is not None and any(cr.is_test_command(c) and not cl.command_failed(c) for c in rest[fixed:]):
            return True
    return False


def proof_6(workspace: Path, trajectory: cl.Trajectory, meta: dict) -> float:
    """Each stage that wrote code saw a test fail for the right reason: test-first red, or broken by hand."""

    def saw_fail(traj: cl.Trajectory, turns: list[tuple[int, int]]) -> float | None:
        calls = [c for span in turns for c in calls_in(traj, span)]
        if not any(writes_source_only(c) for c in calls):
            return None
        return 1.0 if broke_by_hand(calls) or saw_red_first(calls) else 0.0

    return stage_mean(trajectory, meta, saw_fail)


def is_contract_write(call: cl.ToolCall) -> bool:
    """A spec, schema, or types file, or a source write that only declares types or schemas."""
    paths = cl.written_paths(call)
    if any(CONTRACT_PATH_RE.search(p) for p in paths):
        return True
    text = str(call.arguments.get("content") or call.arguments.get("new_string") or "")
    return bool(DECLARATION_RE.search(text)) and not IMPLEMENTATION_RE.search(text)


def default_7(workspace: Path, trajectory: cl.Trajectory, meta: dict) -> float:
    """In each stage that wrote code, the first source write states the contract."""

    def contract_first(traj: cl.Trajectory, turns: list[tuple[int, int]]) -> float | None:
        writes = [c for span in turns for c in calls_in(traj, span) if writes_source_only(c) or is_contract_write(c)]
        if not writes:
            return None
        return 1.0 if is_contract_write(writes[0]) else 0.0

    return stage_mean(trajectory, meta, contract_first)


# Process rules read from the transcript: compatibility, commits, tooling, sign-off, and review.

# A scripted approval that names nothing: human rule 3 limits it to the plan just shown.
GENERIC_APPROVAL_RE = re.compile(r"^\s*(Approved\.?\s*)?Continue\.?\s*$", re.IGNORECASE)
BRANCH_PREFIXES = ("feature/", "fix/", "refactor/")
STAGE_ALL_ARGS = {".", "-A", "--all", "-u", "--update", ":/", "*"}
MAX_SUBJECT = 72
# core rule 7: the static checks a commit waits for, by script name, each with the direct tool calls that also count.
STATIC_CHECKS = {
    "typecheck": re.compile(r"\bnpm\s+run\s+(-\S+\s+)*typecheck\b|\btsc\b"),
    "lint": re.compile(r"\bnpm\s+run\s+(-\S+\s+)*lint\b|\b(eslint|oxlint)\b|\bbiome\s+(check|lint|ci)\b"),
    "format": re.compile(
        r"\bnpm\s+run\s+(-\S+\s+)*format(:check)?\b|\bprettier\s+(--check|-c)\b|\bbiome\s+(check|format|ci)\b"
    ),
}
LINTER_NAMED_RE = re.compile(r"\b(linter|linting|eslint|biome|oxlint)\b", re.IGNORECASE)
VERSION_PIN_FILES = (".nvmrc", ".node-version", ".tool-versions")
EXACT_VERSION_RE = re.compile(r"^v?\d+\.\d+\.\d+$")
DDL_RE = re.compile(r"\b(ALTER|CREATE)\s+TABLE\b", re.IGNORECASE)
MIGRATION_NAMED_RE = re.compile(r"migrat|\bschema\b|\bcolumns?\b|\btables?\b", re.IGNORECASE)
DESTRUCTIVE_GIT = {"reset": "--hard", "clean": "-f", "branch": "-D", "push": "--force", "rebase": ""}
ENV_READ_RE = re.compile(r"process\.env(?:\.([A-Z_][A-Z0-9_]*)|\[\s*['\"]([A-Z_][A-Z0-9_]*)['\"]\s*\])")
RATE_LIMIT_RE = re.compile(
    r"\b429\b|rate.?limit|too.?many.?(requests|attempts)|throttl|lock.?out|login.?attempts|failed.?log.?ins?",
    re.IGNORECASE,
)
REVIEW_PROMPT_RE = re.compile(r"\breview", re.IGNORECASE)


def all_turns(trajectory: cl.Trajectory, meta: dict) -> list[list[tuple[int, int]]]:
    """Each stage's turns; a trial without stage headings is one stage of one turn."""
    stages = stage_turns(trajectory, meta)
    return stages or [[(0, len(trajectory.steps))]]


def user_message(trajectory: cl.Trajectory, span: tuple[int, int]) -> str:
    return str(trajectory.steps[span[0]].get("message") or "") if span[0] < len(trajectory.steps) else ""


def written_text(call: cl.ToolCall) -> str:
    """What a call wrote: a Write's content, an Edit's new text, or the heredoc bodies of a shell write."""
    args = call.arguments
    if call.name == "MultiEdit":
        return "\n".join(str(e.get("new_string") or "") for e in args.get("edits") or [])
    if not cl.is_command_call(call):
        return str(args.get("content") or args.get("new_string") or "")
    return "\n".join(m[4] for m in cl.HEREDOC_RE.finditer(cl.command_text(call))) if cl.written_paths(call) else ""


def git_commands(calls: list[cl.ToolCall]) -> list[tuple[cl.ToolCall, cl.GitInvocation]]:
    return [(call, g) for call in calls for g in cl.git_invocations(call)]


def is_commit(invocation: cl.GitInvocation) -> bool:
    """A commit attempt on the real index. The eval image has no git identity, so git refused many
    attempts; the agent's choices before and in the attempt are what the rules score."""
    return invocation.subcommand == "commit" and not invocation.temp_index


def core_5(workspace: Path, trajectory: cl.Trajectory, meta: dict) -> float | None:
    """Ask before changing behavior stored data depends on: in the stage whose brief changes it
    (consult.json `compat_stage`), a turn's report names the existing data (`compat_terms`) before
    any turn writes code. Raising it in the report of the turn that built it is too late."""
    stage, terms = meta.get("compat_stage"), meta.get("compat_terms")
    if not stage or not terms:
        return None
    stages = stage_turns(trajectory, meta)
    if len(stages) < stage:
        return 0.0
    for span in stages[stage - 1]:
        if any(is_source_write(c) for c in calls_in(trajectory, span)):
            return 0.0
        if re.search(terms, last_message_in(trajectory, span), re.IGNORECASE):
            return 1.0
    return 0.0


def checks_ran_before(calls: list[cl.ToolCall], commit: cl.ToolCall, checks: list[str]) -> float:
    """1.0 when each named check ran after the last source write before the commit, counting a check
    earlier in the commit's own command."""
    upto = [c for c in calls if c.seq < commit.seq]
    last_write = max((c.seq for c in upto if is_source_write(c)), default=-1)
    text = "\n".join(cl.command_text(c) for c in upto if c.seq > last_write and cl.is_command_call(c))
    own = cl.command_text(commit)
    text += "\n" + own[: (m.start() if (m := re.search(r"\bcommit\b", own)) else len(own))]
    return 1.0 if all(STATIC_CHECKS[name].search(text) for name in checks) else 0.0


def core_7(workspace: Path, trajectory: cl.Trajectory, meta: dict) -> float:
    """Static checks before committing, and a missing linter named: the mean of the share of commit
    attempts that ran every check the final package.json defines after the last source write, and
    whether the project has a lint script or a report named the missing linter."""
    scripts = cr.package_scripts(workspace)
    checks = [name for name in STATIC_CHECKS if any(s == name or s.startswith(f"{name}:") for s in scripts)]
    commits = [call for call, g in git_commands(trajectory.calls) if is_commit(g)]
    parts = [1.0 if "lint" in checks or any(LINTER_NAMED_RE.search(m) for m in trajectory.agent_messages) else 0.0]
    if commits:
        parts.append(statistics.fmean(checks_ran_before(trajectory.calls, c, checks) for c in commits))
    return statistics.fmean(parts)


def version_pinned(workspace: Path) -> bool:
    """A language version file, a Volta pin, or an exact `engines.node`."""
    if any((workspace / name).is_file() for name in VERSION_PIN_FILES):
        return True
    try:
        manifest = json.loads((workspace / "package.json").read_text())
    except (OSError, json.JSONDecodeError):
        return False
    engine = str((manifest.get("engines") or {}).get("node") or "")
    return bool((manifest.get("volta") or {}).get("node")) or bool(EXACT_VERSION_RE.match(engine))


def default_11(workspace: Path, trajectory: cl.Trajectory, meta: dict) -> float:
    """Tooling: the mean of one lockfile, the share of test/lint/format/typecheck scripts present, and a pinned
    language version. The package manager is the scaffold's choice (npm), so it is not scored."""
    lockfiles = [name for name in cr.LOCKFILES if (workspace / name).is_file()]
    scripts = cr.package_scripts(workspace)
    wanted = ("test", "lint", "format", "typecheck")
    present = statistics.fmean(1.0 if any(s == w or s.startswith(f"{w}:") for s in scripts) else 0.0 for w in wanted)
    return statistics.fmean([1.0 if len(lockfiles) == 1 else 0.0, present, 1.0 if version_pinned(workspace) else 0.0])


def created_branch(invocation: cl.GitInvocation) -> str | None:
    """The branch a `checkout -b`, `switch -c`, or `git branch <name>` creates."""
    args = invocation.args
    for subcommand, flags in (("checkout", ("-b", "-B")), ("switch", ("-c", "-C", "--create"))):
        if invocation.subcommand == subcommand:
            flag = next((a for a in args if a in flags), None)
            return args[args.index(flag) + 1] if flag and args.index(flag) + 1 < len(args) else None
    if invocation.subcommand == "branch" and args and not args[0].startswith("-"):
        return args[0]
    return None


def stages_everything(invocation: cl.GitInvocation) -> bool:
    """`git add .`/`-A`/`-u`, or a commit with -a: staging without naming files."""
    if invocation.subcommand == "add":
        return bool(STAGE_ALL_ARGS.intersection(invocation.args))
    short_a = any(a.startswith("-") and not a.startswith("--") and "a" in a[1:] for a in invocation.args)
    return invocation.subcommand == "commit" and (short_a or "--all" in invocation.args)


def default_13(workspace: Path, trajectory: cl.Trajectory, meta: dict) -> float | None:
    """Git: the mean of the parts the trial gave something to score. Work on a feature/, fix/, or refactor/
    branch; stage files by name; keep commit subjects under 72 characters; never skip hooks."""
    commands = [g for _, g in git_commands(trajectory.calls)]
    branches = [b for g in commands if (b := created_branch(g))]
    stagings = [g for g in commands if (g.subcommand == "add" and not g.temp_index) or is_commit(g)]
    commits = [g for g in commands if is_commit(g)]
    subjects = [g.message.strip().splitlines()[0] for g in commits if g.message.strip()]
    parts = []
    if branches or commits:
        parts.append(1.0 if branches and all(b.startswith(BRANCH_PREFIXES) for b in branches) else 0.0)
    if stagings:
        parts.append(0.0 if any(stages_everything(g) for g in stagings) else 1.0)
    if subjects:
        parts.append(statistics.fmean(1.0 if len(s) < MAX_SUBJECT else 0.0 for s in subjects))
    if commits:
        parts.append(0.0 if any("--no-verify" in g.args or "-n" in g.args for g in commits) else 1.0)
    return statistics.fmean(parts) if parts else None


PACKAGE_MANAGERS = ("npm", "pnpm", "yarn", "bun")
ADD_COMMANDS = ("install", "i", "add")
PACKAGE_RE = re.compile(r"^(@[a-z0-9._-]+/)?([a-z0-9][a-z0-9._-]*)(@\S*)?$")


def installed_packages(call: cl.ToolCall) -> list[str]:
    """Packages an `npm install <pkg>`-style command adds to the project, by bare name (`@biomejs/biome@2`
    is `biome`). An install after a `cd` out of /app sets up a scratch tool, not a dependency."""
    names, in_workspace = [], True
    for words in cl.shell_commands(call):
        if words[0] == "cd":
            in_workspace = cl._cd_in_workspace(words[1:], in_workspace)
        if in_workspace and len(words) > 2 and words[0] in PACKAGE_MANAGERS and words[1] in ADD_COMMANDS:
            names += [m[2] for w in words[2:] if (m := PACKAGE_RE.match(w.strip("'\"")))]
    return names


def gated_actions(call: cl.ToolCall, schema_built: bool) -> list[re.Pattern]:
    """What in this call needed a yes first, each as the pattern a report must match to have asked:
    a package added, a schema change to an existing database, a push, or a destructive git command."""
    actions = [re.compile(rf"\b{re.escape(name)}\b", re.IGNORECASE) for name in installed_packages(call)]
    if schema_built and is_source_write(call) and DDL_RE.search(written_text(call)):
        actions.append(MIGRATION_NAMED_RE)
    for g in cl.git_invocations(call):
        flag = DESTRUCTIVE_GIT.get(g.subcommand)
        if g.subcommand == "push" or (flag is not None and (not flag or flag in g.args)):
            actions.append(re.compile(rf"\b{g.subcommand}", re.IGNORECASE))
    return actions


def human_2(workspace: Path, trajectory: cl.Trajectory, meta: dict) -> float | None:
    """Stop and ask first: the share of gated actions (a dependency, a migration, a push, a destructive git
    command) taken in a turn after an earlier turn of the same stage named them in its report. A schema
    change counts as a migration from the stage `schema_from_stage` (default 1) on."""
    first = int(meta.get("schema_from_stage", 1))
    asked = []
    for number, turns in enumerate(all_turns(trajectory, meta), 1):
        for index, span in enumerate(turns):
            reports = [last_message_in(trajectory, earlier) for earlier in turns[:index]]
            actions = {a.pattern: a for c in calls_in(trajectory, span) for a in gated_actions(c, number >= first)}
            asked += [1.0 if any(a.search(r) for r in reports) else 0.0 for a in actions.values()]
    return statistics.fmean(asked) if asked else None


def added_extra(call: cl.ToolCall, allowed_env: set[str]) -> bool:
    """Source that reads an environment variable the request did not name, or limits request rates.

    A shell write whose target the parser cannot name (".") counts as source.
    """
    if not (writes_source_only(call) or "." in cl.written_paths(call)):
        return False
    text = written_text(call)
    env = {a or b for a, b in ENV_READ_RE.findall(text)}
    return bool(env - allowed_env) or bool(RATE_LIMIT_RE.search(text))


def human_3(workspace: Path, trajectory: cl.Trajectory, meta: dict) -> float:
    """A generic approval covers only what was just shown: 0 when a turn after a bare "Approved. Continue."
    writes an extra nobody asked for (an unnamed environment variable or a rate limit), else 1."""
    allowed = set(meta.get("allowed_env") or [])
    for turns in all_turns(trajectory, meta):
        for span in turns:
            if not GENERIC_APPROVAL_RE.match(user_message(trajectory, span)):
                continue
            if any(added_extra(c, allowed) for c in calls_in(trajectory, span)):
                return 0.0
    return 1.0


def human_6(workspace: Path, trajectory: cl.Trajectory, meta: dict) -> float:
    """No self-review: no subagent asked to review the change, and no code-review skill loaded."""
    if "code-review" in cl.read_skill_names(trajectory):
        return 0.0
    for call in trajectory.calls:
        prompt = f"{call.arguments.get('description') or ''} {call.arguments.get('prompt') or ''}"
        if call.name in ("Task", "Agent") and REVIEW_PROMPT_RE.search(prompt):
            return 0.0
    return 1.0


CHECKS = {
    "core.simple": shape_check(simplicity),
    **{f"core.simple.s{n}": stage_simplicity(n) for n in range(1, 6)},
    "core.1": shape_check(logic_purity),
    "core.2": core_2,
    "core.4": shape_check(function_shape),
    "core.5": core_5,
    "core.6": probe_check("core.6"),
    "core.7": core_7,
    "default.1": shape_check(default_1),
    "default.2": default_2,
    "default.4": shape_check(default_4),
    "default.5": default_5,
    "default.7": default_7,
    "default.9": default_9,
    "default.10": probe_check("default.10"),
    "default.11": default_11,
    "default.13": default_13,
    "default.follow": default_follow,
    "human.1.stages": human_1_stages,
    "human.2": human_2,
    "human.3": human_3,
    "human.6": human_6,
    "human.7": human_7,
    "proof.6": proof_6,
}
