"""Rule checks for Consult skills, keyed by `<skill>.<rule number>`.

Synced from eval/verifier/shared/consult_rules.py into every task's tests/ by
eval/scripts/sync_tests.py. Do not edit the copy under tests/.

Each check is a function (workspace, trajectory, meta) -> float in [0, 1] that
tests one numbered rule of one SKILL.md. The `rules` dimension scores the ids a
task lists in consult.json `rules`; the step-1 `signoff` suite scores the ids in
SIGNOFF_RULES. `score()` never raises: a crashing check scores 0 and logs why,
because one exception in a RewardKit criterion discards the whole reward.
eval/verifier/rules.json records which rules have a check here.
"""

from __future__ import annotations

import fnmatch
import functools
import json
import re
import shlex
import shutil
import sys
import tempfile
import traceback
from pathlib import Path

# RewardKit imports every .py at the tests root, this one included, before any
# dimension script has put /tests on sys.path.
sys.path.insert(0, str(Path(__file__).resolve().parent))
import consult_lib as cl  # noqa: E402

CONTRACT_RE = re.compile(r"(^|/)openapi\.(ya?ml|json)$")
SCRATCH_RE = re.compile(r"(^|/)(repro|scratch|tmp|debug)[^/]*$|^/")
CODE_RE = re.compile(r"\.[cm]?[jt]sx?$")
CONFIG_CODE_RE = re.compile(r"(^|/)[^/]*\.config\.[cm]?[jt]s$")
# Plans, ADRs, specs, and design notes: what workflow Rule 9 and specify Rule 8
# ask an agent to write. Allowed before sign-off and not "docs" for documentation.1.
PLAN_DOC_RE = re.compile(
    r"(^|/)docs/(plans|adr|decisions|specs?|design)/|(^|/)(PLAN|NOTES)\.md$|(spec|design|plan|adr|decision)[^/]*\.md$",
    re.IGNORECASE,
)
INSTALL_RE = re.compile(r"\b(npm\s+(i|install|ci|add)|pnpm\s+(i|install|add)|yarn(\s+add)?|bun\s+(i|install|add)|npx\s+create-)\b")
TEST_COMMAND_RE = re.compile(r"\b(npm\s+(test|run\s+test)|node\s+--test|vitest|jest|mocha|pytest)\b")
# A reproduction runs the code: a test runner or an interpreter, not grep or cat.
REPRO_COMMAND_RE = re.compile(r"\b(node|npm|npx|pnpm|yarn|bun|deno|vitest|jest|mocha|pytest|python3?)\b")
INCONCLUSIVE_RE = re.compile(r"Cannot find module|ERR_MODULE_NOT_FOUND|SyntaxError")
PROVISIONAL_RE = re.compile(
    r"\bprovisional\b|pending (your )?(approval|sign-?off|confirmation)|until you (approve|confirm)"
    r"|needs? your (approval|sign-?off|confirmation)",
    re.IGNORECASE,
)
LOCKFILES = ("package-lock.json", "pnpm-lock.yaml", "yarn.lock", "bun.lock", "bun.lockb")
TYPECHECKER_RE = re.compile(r"\b(tsc|pyright|mypy|flow)\b")
SKIP_DIRS = {"node_modules", ".git"}


# Shared evidence, computed once per verifier process.


@functools.lru_cache(maxsize=None)
def verification_passed(workspace: Path) -> bool:
    return cl.visible_tests_pass(workspace, cl.load_task_meta()) and cl.hidden_check_passes(workspace)


@functools.lru_cache(maxsize=None)
def probe_results(workspace: Path) -> dict:
    """Per-task runtime probe: tests/rules_probe.mjs prints {"<rule id>": 0|1} on its last line."""
    script = cl.TESTS_DIR / "rules_probe.mjs"
    if not script.exists():
        return {}
    _, output = cl.run_command(workspace, ["node", "--input-type=module", "-e", script.read_text()], timeout=90)
    lines = [line for line in output.strip().splitlines() if line.startswith("{")]
    return json.loads(lines[-1]) if lines else {}


def is_source(path: str) -> bool:
    return cl.classify(path) == "source" and not SCRATCH_RE.search(path) and not CONTRACT_RE.search(path)


def is_code(path: str) -> bool:
    """Application code: a source file with a code extension, not config such as .gitignore or vite.config.ts."""
    return is_source(path) and bool(CODE_RE.search(path)) and not CONFIG_CODE_RE.search(path)


def is_test_command(call: cl.ToolCall) -> bool:
    return cl.is_command_call(call) and bool(TEST_COMMAND_RE.search(cl.command_text(call)))


def is_failed_repro(call: cl.ToolCall) -> bool:
    return cl.command_failed(call) and bool(REPRO_COMMAND_RE.search(cl.command_text(call)))


def writes_matching(call: cl.ToolCall, predicate) -> bool:
    return any(predicate(p) for p in cl.written_paths(call))


def matches_any(path: str, patterns) -> bool:
    return any(fnmatch.fnmatch(path, pattern) for pattern in patterns)


def workspace_files(workspace: Path, suffixes: tuple[str, ...]) -> list[Path]:
    return [
        p for p in workspace.rglob("*")
        if p.is_file() and p.suffix in suffixes and not SKIP_DIRS.intersection(p.relative_to(workspace).parts)
    ]


def package_scripts(workspace: Path) -> dict:
    package = workspace / "package.json"
    return json.loads(package.read_text()).get("scripts") or {} if package.exists() else {}


# debugging


def debugging_1(workspace: Path, trajectory: cl.Trajectory, meta: dict) -> float:
    """Reproduce before fixing: a failing run of the code (a test or an interpreter) before the first code edit."""
    first_fix = cl.first_seq(trajectory, lambda c: writes_matching(c, is_code))
    if first_fix is None:
        return 0.0
    return 1.0 if any(is_failed_repro(c) for c in trajectory.calls if c.seq < first_fix) else 0.0


def debugging_5(workspace: Path, trajectory: cl.Trajectory, meta: dict) -> float:
    """The regression test fails on the scaffold's source and passes on the fix."""
    changed = [p for p in cl.changed_paths(workspace) if (workspace / p).is_file()]
    tests = [p for p in changed if cl.classify(p) == "test"]
    sha = cl.scaffold_sha(workspace)
    fixed = [p for p in changed if is_code(p) and cl.git(workspace, "cat-file", "-t", f"{sha}:{p}").strip()]
    if not tests or not fixed or not meta.get("test_file_cmd"):
        return 0.0
    command = meta["test_file_cmd"].replace("{files}", " ".join(shlex.quote(t) for t in tests))
    passes_after, _ = cl.run_command(workspace, ["bash", "-lc", command], timeout=120)
    if not passes_after:
        return 0.0
    passes_before, output = run_on_scaffold_source(workspace, sha, fixed, command)
    if INCONCLUSIVE_RE.search(output):
        return 0.0
    return 0.0 if passes_before else 1.0


def run_on_scaffold_source(workspace: Path, sha: str, fixed: list[str], command: str) -> tuple[bool, str]:
    """Run command in a copy of the final tree with the fixed source files put back to the scaffold."""
    with tempfile.TemporaryDirectory() as tmp:
        before = Path(tmp) / "before"
        shutil.copytree(workspace, before, symlinks=True, ignore=shutil.ignore_patterns("node_modules"))
        if (workspace / "node_modules").exists():
            (before / "node_modules").symlink_to(workspace / "node_modules")
        for path in fixed:
            (before / path).write_text(cl.git(workspace, "show", f"{sha}:{path}"))
        return cl.run_command(before, ["bash", "-lc", command], timeout=120)


# documentation


def documentation_1(workspace: Path, trajectory: cl.Trajectory, meta: dict) -> float:
    """Docs are not an implementation reflex: no README or reference-doc edit when none was requested."""
    if not verification_passed(workspace):
        return 0.0
    docs = [
        p for p in cl.changed_paths(workspace)
        if (cl.classify(p) == "documentation" or p.startswith("docs/")) and not PLAN_DOC_RE.search(p)
    ]
    return 0.0 if docs else 1.0


# workflow


def workflow_7(workspace: Path, trajectory: cl.Trajectory, meta: dict) -> float:
    """A narrow bug fix needs no sign-off: the one-turn task ends fixed, with a test, instead of stopping to ask.

    A closing offer ("want me to also...?") after finished work is not a stop, so
    the final message is not read; an agent that stopped for sign-off left
    nothing built and fails the verification gate.
    """
    if not verification_passed(workspace):
        return 0.0
    kinds = {cl.classify(p) for p in cl.changed_paths(workspace)}
    return 1.0 if {"source", "test"} <= kinds else 0.0


# api


def api_1(workspace: Path, trajectory: cl.Trajectory, meta: dict) -> float:
    """The contract is sketched before handler code: first contract write precedes first source write."""
    contract = cl.first_seq(trajectory, lambda c: writes_matching(c, lambda p: bool(CONTRACT_RE.search(p))))
    if contract is None:
        return 0.0
    handler = cl.first_seq(trajectory, lambda c: writes_matching(c, is_code))
    return 1.0 if handler is None or contract < handler else 0.0


def api_2(workspace: Path, trajectory: cl.Trajectory, meta: dict) -> float:
    """Shipped fields keep name and type, and the new shape exists (probe)."""
    return float(probe_results(workspace).get("api.2", 0))


def api_3(workspace: Path, trajectory: cl.Trajectory, meta: dict) -> float:
    """Caller errors on the new surface get a 4xx, never a 5xx (probe). Unbuilt code passes this, so gate it."""
    if not verification_passed(workspace):
        return 0.0
    return float(probe_results(workspace).get("api.3", 0))


# domain-modeling


def domain_modeling_11(workspace: Path, trajectory: cl.Trajectory, meta: dict) -> float:
    """Money follows references/money.md: integer minor units or a decimal string beside the currency (probe)."""
    if not verification_passed(workspace):
        return 0.0
    return float(probe_results(workspace).get("domain-modeling.11", 0))


# scaffolding


def scaffolding_5(workspace: Path, trajectory: cl.Trajectory, meta: dict) -> float:
    """test, lint, and typecheck scripts exist and pass; CI, when present, runs them. Partial: no format/coverage."""
    scripts = package_scripts(workspace)
    required = ("test", "lint", "typecheck")
    if not all(name in scripts for name in required):
        return 0.0
    if not all(cl.run_command(workspace, ["npm", "run", name], timeout=180)[0] for name in required):
        return 0.0
    ci_text = " ".join(p.read_text() for p in (workspace / ".github" / "workflows").glob("*.y*ml"))
    return 1.0 if not ci_text or all(name in ci_text for name in required) else 0.0


def scaffolding_6(workspace: Path, trajectory: cl.Trajectory, meta: dict) -> float:
    """typecheck runs a real type checker, not a syntax check."""
    command = package_scripts(workspace).get("typecheck", "")
    return 1.0 if TYPECHECKER_RE.search(command) and "node --check" not in command else 0.0


def scaffolding_7(workspace: Path, trajectory: cl.Trajectory, meta: dict) -> float:
    """Baseline: .gitignore, one unignored lockfile, a smoke test, a full README, .env.example when env is read."""
    lockfiles = [name for name in LOCKFILES if (workspace / name).exists()]
    if not (workspace / ".gitignore").exists() or len(lockfiles) != 1:
        return 0.0
    if cl.git(workspace, "check-ignore", lockfiles[0]).strip():
        return 0.0
    if not any(cl.classify(p) == "test" for p in cl.changed_paths(workspace)):
        return 0.0
    return 1.0 if readme_complete(workspace) and env_example_present(workspace) else 0.0


def readme_complete(workspace: Path) -> bool:
    readme = workspace / "README.md"
    text = readme.read_text().lower() if readme.exists() else ""
    return len(text) > 200 and all(re.search(word, text) for word in (r"install", r"\b(run|start)\b", r"\btest"))


def env_example_present(workspace: Path) -> bool:
    sources = workspace_files(workspace, (".js", ".mjs", ".cjs", ".ts"))
    reads_env = any("process.env" in p.read_text(errors="replace") for p in sources if cl.classify(str(p)) != "test")
    return not reads_env or (workspace / ".env.example").exists()


# Step-1 sign-off checks (run by the brief step's signoff suite, not the rules dimension).


def gated_changes(workspace: Path, meta: dict) -> list[str]:
    gated = meta.get("gated_paths") or ["*"]
    return [p for p in cl.changed_paths(workspace) if matches_any(p, gated) and not PLAN_DOC_RE.search(p)]


def signoff_mode(workspace: Path, trajectory: cl.Trajectory, meta: dict) -> str:
    """stopped: nothing gated changed; provisional: changed and flagged; built: changed silently."""
    if not gated_changes(workspace, meta):
        return "stopped"
    return "provisional" if PROVISIONAL_RE.search(cl.final_agent_message(trajectory)) else "built"


def signoff_score(workspace: Path, trajectory: cl.Trajectory, meta: dict) -> float:
    """workflow Rule 7: stop at the gate, or build a flagged provisional version when no human can answer."""
    return 0.0 if signoff_mode(workspace, trajectory, meta) == "built" else 1.0


def scaffolding_1(workspace: Path, trajectory: cl.Trajectory, meta: dict) -> float:
    """Scaffold Decision Gate: no install and no gated file before approval."""
    installed = any(cl.is_command_call(c) and INSTALL_RE.search(cl.command_text(c)) for c in trajectory.calls)
    if installed or (workspace / "node_modules").exists():
        return 0.0
    return signoff_score(workspace, trajectory, meta)


CHECKS = {
    "api.1": api_1,
    "api.2": api_2,
    "api.3": api_3,
    "debugging.1": debugging_1,
    "debugging.5": debugging_5,
    "documentation.1": documentation_1,
    "domain-modeling.10": signoff_score,
    "domain-modeling.11": domain_modeling_11,
    "scaffolding.1": scaffolding_1,
    "scaffolding.5": scaffolding_5,
    "scaffolding.6": scaffolding_6,
    "scaffolding.7": scaffolding_7,
    "workflow.7": workflow_7,
}
SIGNOFF_RULES = {"scaffolding.1", "domain-modeling.10"}


def score(rule_id: str, workspace: Path) -> float:
    """Run one check; any failure scores 0 and is logged instead of raised."""
    try:
        return float(CHECKS[rule_id](workspace, cl.load_trajectory(), cl.load_task_meta()))
    except Exception:  # noqa: BLE001 - a check must never discard the reward
        sys.stderr.write(f"consult_rules: {rule_id} crashed; scored 0\n{traceback.format_exc()}")
        return 0.0
