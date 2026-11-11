"""Fixtures for house_rules.py and code_shape.mjs: the houseStyle suite's checks.

  python3 -m unittest discover eval/verifier/tests

The analyzer tests need the pinned TypeScript compiler:
`npm ci --prefix eval/verifier/analyzer` (make eval runs it). The staged task's
oracle (steps/s1-approve/solution/reference) must score high on every static
check, and an ordinary layered, class-based, throwing variant
(fixtures/house_style/ordinary) must score low, so the checks separate the two
styles rather than rewarding size.
"""

from __future__ import annotations

import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr
from pathlib import Path
from unittest import mock

EVAL_DIR = Path(__file__).resolve().parents[2]
SHARED = EVAL_DIR / "verifier" / "shared"
ANALYZER_DIR = EVAL_DIR / "verifier" / "analyzer"
TASK = EVAL_DIR / "tasks" / "staged-commissions"
REFERENCE = TASK / "steps" / "s1-approve" / "solution" / "reference"
ORDINARY = Path(__file__).resolve().parent / "fixtures" / "house_style" / "ordinary"
sys.path.insert(0, str(SHARED))
os.environ.setdefault("CONSULT_ANALYZER_DIR", str(ANALYZER_DIR))

import consult_lib as cl
import house_rules as hr

HAS_ANALYZER = (ANALYZER_DIR / "node_modules" / "typescript").is_dir()
NEEDS_ANALYZER = "the analyzer needs `npm ci --prefix eval/verifier/analyzer`"
META = json.loads((TASK / "tests" / "consult.json").read_text())
STATIC_RULES = (
    "core.simple",
    "core.1",
    "core.2",
    "core.4",
    "default.1",
    "default.2",
    "default.4",
    "default.5",
)


def git(root: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True)


def workspace_with(tmp: Path, *overlays: tuple[Path, str]) -> Path:
    """The task scaffold committed in a git repo, with each (source dir, target subdir) copied over it."""
    root = tmp / "app"
    shutil.copytree(TASK / "environment" / "workspace", root)
    git(root, "init", "-q")
    git(root, "add", "-A")
    git(root, "-c", "user.name=t", "-c", "user.email=t@x", "commit", "-qm", "scaffold")
    for source, target in overlays:
        shutil.copytree(source, root / target, dirs_exist_ok=True, ignore=shutil.ignore_patterns("node_modules"))
    return root


def facts_for(tmp: Path, files: dict[str, str]) -> dict:
    for rel, text in files.items():
        (tmp / rel).parent.mkdir(parents=True, exist_ok=True)
        (tmp / rel).write_text(text)
    return hr.shape.__wrapped__(tmp, tuple(sorted(files)))


def static_scores(root: Path) -> dict[str, float]:
    empty = cl.Trajectory(steps=[], calls=[])
    return {rule: hr.CHECKS[rule](root, empty, META) for rule in STATIC_RULES}


@unittest.skipUnless(HAS_ANALYZER, NEEDS_ANALYZER)
class StyleSeparationTests(unittest.TestCase):
    def test_the_oracle_scores_high_on_every_static_check(self):
        with tempfile.TemporaryDirectory() as tmp:
            scores = static_scores(workspace_with(Path(tmp), (REFERENCE, ".")))

        self.assertEqual({r: s for r, s in scores.items() if s < 0.7}, {})
        self.assertGreaterEqual(scores["core.simple"], 0.9)

    def test_an_ordinary_layered_class_based_variant_scores_low(self):
        with tempfile.TemporaryDirectory() as tmp:
            scores = static_scores(workspace_with(Path(tmp), (ORDINARY, ".")))

        for rule in ("core.1", "default.1", "default.4", "default.5"):
            self.assertEqual(scores[rule], 0.0, rule)
        self.assertLess(scores["core.simple"], 0.75)
        self.assertLess(scores["default.2"], 0.5)

    def test_nothing_built_scores_zero_not_a_vacuous_one(self):
        with tempfile.TemporaryDirectory() as tmp:
            scores = static_scores(workspace_with(Path(tmp)))

        self.assertEqual(scores["core.simple"], 0.0)
        self.assertEqual(scores["default.1"], 0.0)


CONTROL = EVAL_DIR / "tasks" / "follow-the-project"
CONTROL_META = json.loads((CONTROL / "tests" / "consult.json").read_text())
IMPOSED = Path(__file__).resolve().parent / "fixtures" / "house_style" / "imposed"


def control_workspace(tmp: Path, overlay: Path) -> Path:
    root = tmp / "app"
    shutil.copytree(CONTROL / "environment" / "workspace", root)
    git(root, "init", "-q")
    git(root, "add", "-A")
    git(root, "-c", "user.name=t", "-c", "user.email=t@x", "commit", "-qm", "scaffold")
    shutil.copytree(overlay, root, dirs_exist_ok=True)
    return root


@unittest.skipUnless(HAS_ANALYZER, NEEDS_ANALYZER)
class FollowTheProjectTests(unittest.TestCase):
    def score(self, overlay: Path) -> float:
        with tempfile.TemporaryDirectory() as tmp:
            root = control_workspace(Path(tmp), overlay)
            return hr.default_follow(root, cl.Trajectory(steps=[], calls=[]), CONTROL_META)

    def test_building_the_way_the_project_already_does_scores_one(self):
        self.assertEqual(self.score(CONTROL / "steps" / "approve" / "solution" / "files"), 1.0)

    def test_imposing_the_house_style_on_a_project_that_chose_otherwise_scores_low(self):
        self.assertLess(self.score(IMPOSED), 0.3)


# The names lift.py reads (lift.STAGE_PARTS); test_lift.py checks its side.
STAGE_PARTS = ("function_shape", "logic_purity", "state_isolation", "acyclic_imports", "no_speculative_abstraction")


def snapshot(source: Path, target: Path) -> None:
    """A step verifier's snapshot: the tree without .git."""
    shutil.copytree(source, target, ignore=shutil.ignore_patterns(".git", "node_modules"))


class StageShapeTests(unittest.TestCase):
    """stage-shape.json, the per-stage readout core.simple.s<k> writes beside the verifier details."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.details = self.tmp / "stage-shape.json"
        for name, value in (("SNAPSHOTS_DIR", self.tmp / "snapshots"), ("STAGE_SHAPE_PATH", self.details)):
            patcher = mock.patch.object(hr, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def stage_scores(self, root: Path) -> dict[int, float]:
        empty = cl.Trajectory(steps=[], calls=[])
        return {n: hr.CHECKS[f"core.simple.s{n}"](root, empty, META) for n in range(1, 6)}

    def recorded(self) -> dict:
        return json.loads(self.details.read_text())

    def test_lines_split_into_source_tests_and_specs_without_blank_lines_or_vendored_folders(self):
        files = {
            "src/orders/order.ts": "const a = 1;\n\n  \nexport { a };\n",
            "src/orders/order.test.ts": "test();\n",
            "test/api.test.ts": "one();\ntwo();\n",
            "openapi.yaml": "openapi: 3.1.0\ninfo: {}\npaths: {}\n",
            "db/schema.sql": "CREATE TABLE t (id INTEGER);\n",
            "README.md": "# Orders\n\nText.\n",
            "src/types.d.ts": "declare const x: number;\n",
            "package.json": "{}\n",
            "catalogue.json": "[]\n",
            "node_modules/dep/index.js": "module.exports = 1;\n",
            "dist/main.js": "built();\n",
        }
        for rel, text in files.items():
            (self.tmp / rel).parent.mkdir(parents=True, exist_ok=True)
            (self.tmp / rel).write_text(text)

        self.assertEqual(hr.line_counts(self.tmp), {"source": 2, "test": 3, "spec": 6})

    @unittest.skipUnless(HAS_ANALYZER, NEEDS_ANALYZER)
    def test_each_stage_with_a_snapshot_records_its_lines_and_the_parts_its_score_averages(self):
        snapshot(workspace_with(self.tmp / "scaffold"), self.tmp / "snapshots" / "2")  # stage 1 built nothing
        workspace = workspace_with(self.tmp, (REFERENCE, "."))
        snapshot(workspace, self.tmp / "snapshots" / "5")  # stage 2 left the reference

        scores = self.stage_scores(workspace)
        stages = self.recorded()

        self.assertEqual(set(stages), {"1", "2", "5"})
        self.assertIsNone(stages["1"]["parts"])
        self.assertEqual(scores[1], 0.0)
        self.assertEqual(scores[3], 0.0)
        self.assertGreater(stages["2"]["lines"]["source"], stages["1"]["lines"]["source"])
        self.assertGreater(stages["2"]["lines"]["test"], 0)
        self.assertEqual(stages["2"], stages["5"])
        self.assertEqual(set(stages["5"]["parts"]), set(STAGE_PARTS))
        self.assertAlmostEqual(scores[5], sum(stages["5"]["parts"].values()) / 5)
        self.assertEqual(scores[5], hr.CHECKS["core.simple"](workspace, cl.Trajectory(steps=[], calls=[]), META))

    @unittest.skipUnless(HAS_ANALYZER, NEEDS_ANALYZER)
    def test_without_snapshots_only_the_final_tree_is_recorded(self):
        # As in an offline rescore, which does not rebuild /opt/eval/snapshots.
        workspace = workspace_with(self.tmp, (REFERENCE, "."))

        scores = self.stage_scores(workspace)

        self.assertEqual([scores[n] for n in range(1, 5)], [0.0] * 4)
        self.assertEqual(set(self.recorded()), {"5"})

    @unittest.skipUnless(HAS_ANALYZER, NEEDS_ANALYZER)
    def test_a_details_file_that_cannot_be_written_leaves_the_score_unchanged(self):
        workspace = workspace_with(self.tmp, (REFERENCE, "."))
        expected = hr.CHECKS["core.simple"](workspace, cl.Trajectory(steps=[], calls=[]), META)

        unwritable = self.tmp / "missing" / "stage-shape.json"
        with mock.patch.object(hr, "STAGE_SHAPE_PATH", unwritable), redirect_stderr(io.StringIO()) as err:
            score = self.stage_scores(workspace)[5]

        self.assertEqual(score, expected)
        self.assertIn("could not record stage 5", err.getvalue())


@unittest.skipUnless(HAS_ANALYZER, NEEDS_ANALYZER)
class AnalyzerFactTests(unittest.TestCase):
    def analyze(self, source: str) -> dict:
        with tempfile.TemporaryDirectory() as tmp:
            return facts_for(Path(tmp), {"src/a.ts": source})

    def function(self, facts: dict, name: str) -> dict:
        return next(f for f in facts["functions"] if f["name"] == name)

    def test_a_boolean_flag_joined_to_a_comparison_is_an_unnamed_compound(self):
        facts = self.analyze("export function f(a: boolean, n: number) { if (a && n > 1) return 1; return 0; }")

        self.assertEqual(self.function(facts, "f")["compound"], 1)

    def test_null_checks_and_result_plumbing_need_no_name(self):
        source = "type R = { ok: true } | { ok: false };\nexport function f(r: R, x?: string[]) { if (!r.ok || !x || x.length === 0) return 1; return 0; }"

        self.assertEqual(self.function(self.analyze(source), "f")["compound"], 0)

    def test_an_else_if_chain_is_one_level_and_nested_loops_count(self):
        source = (
            "export function chain(n: number) { if (n > 1) return 1; else if (n > 0) return 2; else return 3; }\n"
            "export function deep(xs: number[][]) { for (const x of xs) { for (const y of x) { if (y) return y; } } return 0; }"
        )
        facts = self.analyze(source)

        self.assertEqual(self.function(facts, "chain")["nesting"], 1)
        self.assertEqual(self.function(facts, "deep")["nesting"], 3)

    def test_impurity_follows_calls_and_ignores_regexp_exec(self):
        source = (
            'import { readFileSync } from "node:fs";\n'
            "export function load() { return readFileSync('x', 'utf8'); }\n"
            "export function viaLoad() { return load().length; }\n"
            "export function parse(s: string) { return /a(b)/.exec(s)?.[1]; }"
        )
        facts = self.analyze(source)

        self.assertFalse(self.function(facts, "viaLoad")["pure"])
        self.assertTrue(self.function(facts, "parse")["pure"])

    def test_module_state_mutated_by_a_function_is_shared_mutable_state(self):
        facts = self.analyze("let hits = 0;\nexport function count() { hits += 1; return hits; }")

        self.assertEqual(facts["sharedMutable"], [{"file": "src/a.ts", "name": "hits"}])

    def test_rethrowing_the_caught_error_is_not_an_expected_failure(self):
        source = (
            "export function f(g: () => void) { try { g(); } catch (error) { throw error; } }\n"
            "class Negative extends Error {}\n"
            "export function h(n: number) { if (n < 0) throw new Negative('negative'); return n; }"
        )
        throws = {t["function"]: t["expected"] for t in self.analyze(source)["throws"]}

        self.assertEqual(throws, {"f": False, "h": True})

    def test_plain_built_in_errors_are_bug_checks_and_custom_classes_are_expected_failures(self):
        # Messages from houseStyle consult trials, which rule 4 allows as bug checks.
        source = (
            "class HttpError extends Error {}\n"
            "export function withdraw(id: number) { if (id < 0) throw new Error('Commission 7 is withdrawn with no restocking fee'); return id; }\n"
            "export function convert(n: number) { if (n > 9) throw new RangeError('cannot subtract across currencies'); return n; }\n"
            "export function show(id: number) { if (id === 0) throw new HttpError('not found'); return id; }"
        )
        throws = self.analyze(source)["throws"]

        self.assertEqual(
            {t["function"]: t["expected"] for t in throws}, {"withdraw": False, "convert": False, "show": True}
        )
        self.assertEqual(hr.default_4({"resultLibrary": "neverthrow", "throws": throws}), 0.5)
        self.assertEqual(hr.default_4({"resultLibrary": "neverthrow", "throws": throws[:2]}), 1.0)

    def test_intersection_variants_are_explicit_state_variants(self):
        source = (
            "type Base = { id: string };\n"
            "export type C = (Base & { status: 'a' }) | (Base & { status: 'b'; ref: string }) | (Base & { status: 'c'; fee: number });"
        )
        union = next(u for u in self.analyze(source)["unions"] if u["name"] == "C")

        self.assertEqual(
            (union["discriminant"], union["variants"], union["specificVariants"], union["result"]),
            ("status", 3, 2, False),
        )


class PathAndNameTests(unittest.TestCase):
    def test_technical_role_folders_are_layers_and_feature_folders_are_not(self):
        self.assertTrue(hr.is_layered("src/services/orders.ts"))
        self.assertTrue(hr.is_layered("src/types.ts"))
        self.assertFalse(hr.is_layered("src/commissions/types.ts"))
        self.assertFalse(hr.is_layered("src/http/server.ts"))

    def test_the_report_order_rewards_all_five_sections_in_order(self):
        ordered = (
            "## Needs your attention\nx\n## What changed\ny\n## How it works\nz\n## What proves it\nw\n## Unproven\nv"
        )
        shuffled = "## What changed\ny\n## Needs your attention\nx\n## Tests\nw"

        self.assertEqual(hr.report_order(ordered), 1.0)
        self.assertEqual(hr.report_order(shuffled), 0.3)


def user(message: str) -> dict:
    return {"source": "user", "message": message}


def agent(message: str = "", *calls: dict) -> dict:
    return {"source": "agent", "message": message, "tool_calls": list(calls)}


def write(path: str, content: str = "x") -> dict:
    return {
        "tool_call_id": f"w{path}{content}",
        "function_name": "Write",
        "arguments": {"file_path": f"/app/{path}", "content": content},
    }


def edit(path: str, old: str, new: str) -> dict:
    return {
        "tool_call_id": f"e{old}{new}",
        "function_name": "Edit",
        "arguments": {"file_path": f"/app/{path}", "old_string": old, "new_string": new},
    }


def bash(call_id: str, command: str) -> dict:
    return {"tool_call_id": call_id, "function_name": "Bash", "arguments": {"command": command}}


def npm_test(call_id: str) -> dict:
    return {"tool_call_id": call_id, "function_name": "Bash", "arguments": {"command": "npm test"}}


def build(steps: list[dict]) -> cl.Trajectory:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "trajectory.json"
        path.write_text(json.dumps({"steps": list(steps)}))
        return cl.load_trajectory(path)


STAGED = {**META, "stage_headings": ["# One", "# Two"]}


class StageTests(unittest.TestCase):
    def test_turns_split_at_headings_and_approvals_not_at_skill_bodies(self):
        traj = build(
            [
                user("# One\nbrief"),
                user("Base directory for this skill: x"),
                agent(),
                user("Approved, build it."),
                agent(),
                user("# Two\nmore"),
                agent(),
            ]
        )

        self.assertEqual(hr.stage_turns(traj, STAGED), [[(0, 3), (3, 5)], [(5, 7)]])

    def test_a_brief_turn_that_writes_source_without_flagging_it_fails_the_checkpoint(self):
        traj = build(
            [
                user("# One"),
                agent("Plan: ..."),
                user("Approved"),
                agent("", write("src/a.ts")),
                user("# Two"),
                agent("Done.", write("src/b.ts")),
            ]
        )

        self.assertEqual(hr.human_1_stages(Path("/nonexistent"), traj, STAGED), 0.5)

    def test_breaking_by_hand_is_an_edit_a_failing_run_and_its_exact_reversal(self):
        steps = [
            user("# One"),
            agent("", write("src/fee.ts", "export const fee = 2;"), npm_test("t1")),
            agent("", edit("src/fee.ts", "fee = 2", "fee = 3"), npm_test("t2")),
            agent("", edit("src/fee.ts", "fee = 3", "fee = 2"), npm_test("t3")),
        ]

        self.assertEqual(hr.proof_6(Path("/nonexistent"), build_failing(steps, {"t2"}), STAGED), 1.0)

    def test_tests_that_only_ever_passed_saw_nothing_fail(self):
        steps = [user("# One"), agent("", write("src/fee.ts"), write("src/fee.test.ts"), npm_test("t1"))]

        self.assertEqual(hr.proof_6(Path("/nonexistent"), build_failing(steps, set()), STAGED), 0.0)

    def test_a_types_only_write_first_is_contract_first(self):
        first = write("src/commissions/commission.ts", "export type Commission = { id: string };")
        then = write("src/commissions/routes.ts", "export function place() { return 1; }")
        traj = build([user("# One"), agent("", first, then), user("# Two"), agent("", then)])

        self.assertEqual(hr.default_7(Path("/nonexistent"), traj, STAGED), 0.5)

    def test_a_spec_rewritten_by_an_inline_script_before_source_is_contract_first(self):
        # Trial NfBj5ow edited openapi.yaml this way in stages 2-5.
        rewrite = bash(
            "b1",
            "python3 - <<'EOF'\nfrom pathlib import Path\np = Path(\"openapi.yaml\")\n"
            's = p.read_text()\np.write_text(s + "\\n")\nEOF',
        )
        scratch = bash("b2", "cat > /tmp/probe.ts <<'EOF'\nexport function probe() { return 1; }\nEOF")
        routes = write("src/commissions/routes.ts", "export function place() { return 1; }")
        traj = build([user("# One"), agent("", scratch, rewrite, routes)])

        self.assertEqual(hr.default_7(Path("/nonexistent"), traj, STAGED), 1.0)


COMPAT = {**STAGED, "compat_stage": 2, "compat_terms": r"\b(placed before|older orders?)\b"}
CONTINUE = "Approved. Continue."
APPROVE = "Approved, including the interface and data shapes you proposed. Build it."


def project(tmp: Path, scripts: dict, *files: str) -> Path:
    """A workspace holding only a package.json with these scripts and the named empty files."""
    (tmp / "package.json").write_text(json.dumps({"scripts": scripts, "engines": {"node": ">=22.18"}}))
    for name in files:
        (tmp / name).write_text("")
    return tmp


class GitParsingTests(unittest.TestCase):
    def test_git_is_found_through_variables_arrays_and_global_options(self):
        # Bare trials 8crP9T9 and 3Gz8h4S committed this way to supply an identity.
        command = (
            'G="git -c user.name=eval -c user.email=eval@example.com"\n$G switch -c gift-cards\n'
            "ID=(-c user.name=eval)\ngit \"${ID[@]}\" commit -q -F - <<'EOF'\nAdd gift cards\n\nBody.\nEOF"
        )
        calls = build([user("# One"), agent("", bash("b1", command))]).calls
        found = [(g.subcommand, g.message.splitlines()[0] if g.message else "") for g in cl.git_invocations(calls[0])]

        self.assertEqual(found, [("switch", ""), ("commit", "Add gift cards")])

    def test_a_scratch_index_holds_until_unset(self):
        # Consult trials snapshot slices with a temporary index; that stages nothing for review.
        command = "export GIT_INDEX_FILE=/tmp/s.index; git add -A .; unset GIT_INDEX_FILE; git add src/a.ts"
        calls = build([user("# One"), agent("", bash("b1", command))]).calls

        self.assertEqual([g.temp_index for g in cl.git_invocations(calls[0])], [True, False])


class ProcessRuleTests(unittest.TestCase):
    def test_naming_existing_data_before_building_the_stage_passes_compatibility(self):
        # Consult trial mRjy2Ce: "how customers paid for orders placed before today".
        asked = build(
            [
                user("# One"),
                agent("Built.", write("src/a.ts")),
                user("# Two"),
                agent("One thing the request can't tell me: how customers paid for orders placed before today."),
                user(APPROVE),
                agent("Done.", write("src/b.ts")),
            ]
        )
        # Bare trial 3Gz8h4S built first, then reported "Older orders show `null`".
        told = build(
            [user("# One"), agent("Built."), user("# Two"), agent("Older orders show null.", write("src/b.ts"))]
        )

        self.assertEqual(hr.core_5(Path("/nonexistent"), asked, COMPAT), 1.0)
        self.assertEqual(hr.core_5(Path("/nonexistent"), told, COMPAT), 0.0)
        no_question = {k: v for k, v in STAGED.items() if not k.startswith("compat_")}
        self.assertIsNone(hr.core_5(Path("/nonexistent"), asked, no_question))

    def test_a_commit_after_the_type_check_with_the_missing_linter_named_passes(self):
        checked = [
            user("# One"),
            agent("", write("src/a.ts")),
            agent(
                "The project has no linter or formatter.",
                bash("b1", "npm run typecheck"),
                bash("b2", "git commit -m 'Add a'"),
            ),
        ]
        unchecked = [
            user("# One"),
            agent("Done.", write("src/a.ts"), bash("b1", "git add -A && git commit -m 'Add a'")),
        ]
        with tempfile.TemporaryDirectory() as tmp:
            workspace = project(Path(tmp), {"test": "node --test", "typecheck": "tsc --noEmit"})

            self.assertEqual(hr.core_7(workspace, build(checked), STAGED), 1.0)
            self.assertEqual(hr.core_7(workspace, build(unchecked), STAGED), 0.0)

    def test_tooling_readout_needs_one_lockfile_four_scripts_and_a_pinned_version(self):
        scripts = {"test": "a", "lint": "b", "format": "c", "typecheck": "d"}
        with tempfile.TemporaryDirectory() as full, tempfile.TemporaryDirectory() as scaffold:
            complete = project(Path(full), scripts, "package-lock.json", ".nvmrc")
            as_given = project(Path(scaffold), {"test": "a", "typecheck": "d"}, "package-lock.json")

            self.assertEqual(hr.default_tooling(complete, build([]), STAGED), 1.0)
            self.assertEqual(hr.default_tooling(as_given, build([]), STAGED), 0.5)

    def test_git_conventions_score_the_branch_staging_subject_and_hooks(self):
        # Consult trials: a feature/ branch and files staged by name.
        consult = bash("b1", "git checkout -b feature/gift-cards && git add src/a.ts && git commit -m 'Add gift cards'")
        # Bare trial L5BDNZh: an untyped branch and `git add -A`.
        bare = bash("b2", "git switch -c gift-cards && git add -A && git commit -m 'Add gift cards'")
        snapshot = bash("b3", "GIT_INDEX_FILE=/tmp/x git add -A && git checkout -b fix/total")

        self.assertEqual(hr.default_13(Path("/nonexistent"), build([user("# One"), agent("", consult)]), STAGED), 1.0)
        self.assertEqual(hr.default_13(Path("/nonexistent"), build([user("# One"), agent("", bare)]), STAGED), 0.5)
        self.assertEqual(hr.default_13(Path("/nonexistent"), build([user("# One"), agent("", snapshot)]), STAGED), 1.0)
        self.assertIsNone(hr.default_13(Path("/nonexistent"), build([user("# One"), agent("Done.")]), STAGED))

    def test_a_dependency_or_migration_needs_an_earlier_report_in_the_stage_that_named_it(self):
        install = bash("b1", "npm install --save-exact zod@4.6.7 2>&1 | tail -3")
        migration = write("src/database.ts", "db.exec(`ALTER TABLE commissions ADD COLUMN deposit INTEGER`);")
        scratch = bash("b2", "mkdir -p /tmp/spec && cd /tmp/spec && npm install --silent ajv")
        meta = {**STAGED, "schema_from_stage": 2}
        asked = build(
            [
                user("# One"),
                agent("Plan: validate with zod."),
                user(APPROVE),
                agent("Done.", install),
                user("# Two"),
                agent("Plan: one new column for the deposit."),
                user(APPROVE),
                agent("Done.", migration),
            ]
        )
        # Only a report in the same stage counts: stage one's mention of its schema asked nothing about stage two.
        unasked = build(
            [user("# One"), agent("The schema has one table."), user("# Two"), agent("Added a column.", migration)]
        )

        self.assertEqual(hr.human_2(Path("/nonexistent"), asked, meta), 1.0)
        self.assertEqual(hr.human_2(Path("/nonexistent"), unasked, meta), 0.0)
        self.assertIsNone(hr.human_2(Path("/nonexistent"), build([user("# One"), agent("", scratch)]), meta))

    def test_an_extra_built_after_a_generic_approval_fails_but_one_in_the_approved_plan_passes(self):
        # Bare trial 3Gz8h4S built a log-in limit on "Approved. Continue."
        limiter = write("src/throttle.ts", "// Limits how many log-in attempts.\nexport const status = 429;")
        after_continue = build(
            [user("# One"), agent("Plan."), user(APPROVE), agent("Built."), user(CONTINUE), agent("", limiter)]
        )
        in_the_plan = build([user("# One"), agent("Plan, with a log-in limit."), user(APPROVE), agent("", limiter)])
        fix = build([user("# One"), agent("Built."), user(CONTINUE), agent("", write("src/a.ts", "process.env.PORT"))])
        meta = {**STAGED, "allowed_env": ["PORT"]}

        self.assertEqual(hr.human_3(Path("/nonexistent"), after_continue, meta), 0.0)
        self.assertEqual(hr.human_3(Path("/nonexistent"), in_the_plan, meta), 1.0)
        self.assertEqual(hr.human_3(Path("/nonexistent"), fix, meta), 1.0)


class RemoteCallTests(unittest.TestCase):
    """default.9 from the rule probe's output (patched here; the probe itself needs a running app)."""

    def score(self, root: Path, probe: dict) -> float:
        with mock.patch.object(hr.cr, "probe_results", return_value=probe):
            return hr.default_9(root, cl.Trajectory(steps=[], calls=[]), META)

    def test_the_oracle_retries_transient_failures_with_jitter_and_scores_one(self):
        # What the probe prints for the oracle reference.
        with tempfile.TemporaryDirectory() as tmp:
            root = workspace_with(Path(tmp), (REFERENCE, "."))

            self.assertEqual(self.score(root, {"default.9": 1, "default.9.retried": 1}), 1.0)

    def test_a_timeout_without_a_retry_scores_one(self):
        # The oracle with ATTEMPTS = 1: the brief asks for no retry, so none is rewarded.
        with tempfile.TemporaryDirectory() as tmp:
            root = workspace_with(Path(tmp), (REFERENCE, "."))

            self.assertEqual(self.score(root, {"default.9": 1, "default.9.retried": 0}), 1.0)

    def test_a_retry_is_held_to_jitter_and_to_sparing_permanent_failures(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "src").mkdir()
            (root / "src" / "rates.ts").write_text("export const get = (url: string) => fetch(url);\n")

            self.assertEqual(self.score(root, {"default.9": 1, "default.9.retried": 1}), 0.75)
            self.assertEqual(self.score(root, {"default.9": 0.5, "default.9.retried": 1}), 0.375)

    def test_the_ordinary_variant_has_no_rates_call_and_scores_zero(self):
        # The probe cannot place a commission or read rates there, so it prints {}.
        with tempfile.TemporaryDirectory() as tmp:
            root = workspace_with(Path(tmp), (ORDINARY, "."))

            self.assertEqual(self.score(root, {}), 0.0)


def build_failing(steps: list[dict], failing: set[str]) -> cl.Trajectory:
    for step in steps:
        ids = [c["tool_call_id"] for c in step.get("tool_calls") or []]
        results = [{"source_call_id": i, "content": "Exit code 1\nnot ok 1" if i in failing else "ok"} for i in ids]
        step["observation"] = {"results": results}
    return build(steps)


if __name__ == "__main__":
    unittest.main()
