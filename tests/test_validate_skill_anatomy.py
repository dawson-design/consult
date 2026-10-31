"""The skill anatomy validator's CLI: what it accepts, and each finding it reports.

Every test builds a scratch repo (skills, plugin mirror, plugin manifests,
rule coverage) and runs the validator on it, asserting on its output and
exit status.
"""

from __future__ import annotations

import json
import shutil
import unittest
from pathlib import Path
from typing import Any

from helpers import ROOT, TempDirTestCase, run

# The implementation under test. Step 4 of docs/plans/python-only-tooling.md
# switches this to the Python port.
COMMAND = ["node", ROOT / "scripts/validate-skill-anatomy.mjs"]

# Step 3 of the plan reads HOOK_SOURCE and render_session_start_hooks from
# the Python generator instead.
HOOK_SOURCE = "agents/.agents/skills/workflow/references/core.md"
GENERATOR = ROOT / "scripts/generate-plugin-symlinks.mjs"

GOOD_SKILL = """---
name: good
description: Good test skill
---

# Good

## When to Use

- trigger
- one change per commit

## When NOT to Use

- other

## Rules

1. check

## Workflow

1. Do the first relevant action.
2. Run the smallest check that proves the claim.
3. Report the evidence and any blocker.
4. Keep changes scoped to the request.

## Tripwires

| Trigger | Do this instead | False alarm |
|---|---|---|
| "Skip the check" | Run the check before making a completion claim. | Research notes with no completion claim. |
"""

BAD_SKILL = """---
name: bad
description: Bad test skill
---

# Bad

Per Rich Hickey, prefer values over places.

## Overview

Stuff.

## Common Rationalizations

| Excuse | Reality |
|---|---|
| "Should work" | It might not. |

## Red Flags

- "Probably fine"
"""

LONG_TRIPWIRES_SKILL = """---
name: long-tripwires
description: Long tripwire table
---

# Long Tripwires

## When to Use

- trigger

## When NOT to Use

- other

## Rules

1. check

## Tripwires

| Trigger | Do this instead | False alarm |
|---|---|---|
""" + "".join(f'| "Shortcut {n}" | Do the thing. | None. |\n' for n in range(1, 10))

EM_DASH_SKILL = """---
name: dashy
description: Em dash and drifted approval sentence fixture
---

# Dashy

An approving design or RFC is not this approval — the phrasing drifted.

## When to Use

- trigger

## When NOT to Use

- other

## Rules

1. check
"""

ROUTER_SKILL = """---
name: workflow
description: Router fixture
---

# Workflow

## When to Use

- always

## When NOT to Use

- never

## Rules

1. check

## Workflow

   | Skill | Load when |
   | --- | --- |
   | `good` | always |
   | `ghost-skill` | never |
"""

HOOK_CORE = "Consult is installed. Load the consult:workflow skill.\n"

# Passed as plugin_hooks to write the hook source and a hooks.json generated from it.
GENERATED = "generated"


def write_json(path: Path, value: Any) -> None:
    """Write `value` as JSON to `path`, creating parent directories."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf8")


def render_session_start_hooks(core: str) -> str:
    """Return the hooks.json text the generator renders for `core`."""
    script = (
        f"import {{ renderSessionStartHooks }} from {json.dumps(GENERATOR.as_uri())};"
        "process.stdout.write(renderSessionStartHooks(process.argv[1]));"
    )
    result = run(["node", "--input-type=module", "-e", script, core])
    if result.returncode != 0:
        raise RuntimeError(result.stderr)
    return result.stdout


def write_hook_source(root: Path, text: str = HOOK_CORE) -> None:
    """Write core.md and its plugin/skills mirror copy, so the fixture passes both drift checks."""
    mirror_path = HOOK_SOURCE.replace("agents/.agents/skills/", "plugin/skills/")
    for rel in [HOOK_SOURCE, mirror_path]:
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_text(text, encoding="utf8")


def write_generated_hooks(root: Path, core: str = HOOK_CORE) -> None:
    """Write plugin/hooks/hooks.json as the generator renders it for `core`."""
    path = root / "plugin/hooks/hooks.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_session_start_hooks(core), encoding="utf8")


def make_skill(skills_dir: Path, name: str, body: str = GOOD_SKILL) -> Path:
    """Write `body` as `skills_dir/name/SKILL.md` and return the skill directory."""
    skill = skills_dir / name
    skill.mkdir(parents=True, exist_ok=True)
    (skill / "SKILL.md").write_text(body, encoding="utf8")
    return skill


def write_codex_marketplace(root: Path, source_path: str, policy: bool, category: bool) -> None:
    """Write .agents/plugins/marketplace.json with the chosen fields."""
    entry: dict[str, Any] = {"name": "consult", "source": {"source": "local", "path": source_path}}
    if policy:
        entry["policy"] = {"installation": "AVAILABLE", "authentication": "ON_INSTALL"}
    if category:
        entry["category"] = "Coding"
    marketplace = {"name": "consult", "interface": {"displayName": "Consult"}, "plugins": [entry]}
    write_json(root / ".agents/plugins/marketplace.json", marketplace)


def write_codex_manifest(root: Path, version: str, skills_path: str, hooks: bool) -> None:
    """Write plugin/.codex-plugin/plugin.json, optionally declaring hooks."""
    manifest: dict[str, Any] = {
        "name": "consult",
        "version": version,
        "skills": skills_path,
        "interface": {
            "displayName": "Consult",
            "category": "Coding",
            "capabilities": ["Read", "Write"],
            "defaultPrompt": ["Use Consult workflow for this engineering task."],
        },
    }
    if hooks:
        manifest["hooks"] = "./hooks.json"
    write_json(root / "plugin/.codex-plugin/plugin.json", manifest)


def write_claude_files(root: Path, versions: dict[str, str], hooks: bool) -> None:
    """Write the Claude marketplace and manifest; `hooks` adds a Stop hook to the manifest."""
    marketplace = {
        "name": "consult",
        "metadata": {"version": versions["marketplace"]},
        "plugins": [{"name": "consult", "version": versions["entry"], "source": "./plugin"}],
    }
    write_json(root / ".claude-plugin/marketplace.json", marketplace)
    manifest: dict[str, Any] = {"name": "consult", "version": versions["manifest"]}
    if hooks:
        command = "node ${CLAUDE_PLUGIN_ROOT}/scripts/self-review.mjs"
        handler = {"type": "command", "command": command, "timeout": 5}
        manifest["hooks"] = {"Stop": [{"matcher": "*", "hooks": [handler]}]}
    write_json(root / "plugin/.claude-plugin/plugin.json", manifest)


def write_cursor_files(root: Path, versions: dict[str, str], skills_path: str, hooks: bool) -> None:
    """Write the Cursor marketplace and manifest, optionally declaring hooks."""
    marketplace = {
        "name": "consult",
        "owner": {"name": "Dawson Design Ltd.", "url": "https://github.com/dawson-design"},
        "metadata": {"version": versions["marketplace"]},
        "plugins": [{"name": "consult", "version": versions["entry"], "source": "./plugin"}],
    }
    write_json(root / ".cursor-plugin/marketplace.json", marketplace)
    manifest: dict[str, Any] = {"name": "consult", "version": versions["manifest"], "skills": skills_path}
    if hooks:
        manifest["hooks"] = "./hooks.json"
    write_json(root / "plugin/.cursor-plugin/plugin.json", manifest)


def make_plugin_packages(
    root: Path,
    *,
    include_marketplace: bool = True,
    include_manifest: bool = True,
    marketplace_source_path: str = "./plugin",
    include_policy: bool = True,
    include_category: bool = True,
    manifest_skills_path: str = "./skills/",
    codex_hooks: bool = False,
    claude_hooks: bool = False,
    cursor_hooks: bool = False,
    codex_version: str = "2.0.0",
    claude_versions: dict[str, str] | None = None,
    plugin_hooks: dict[str, Any] | str | None = GENERATED,
) -> None:
    """Write the hooks file and the Codex, Claude, and Cursor plugin packages.

    `plugin_hooks` is GENERATED (core.md plus the hooks.json rendered from
    it), a dict written as hooks.json with no core.md, or None for neither.
    `claude_versions` sets the marketplace, entry, and manifest versions used
    by both the Claude and Cursor files (default: all "2.0.0").
    """
    versions = claude_versions or {"marketplace": "2.0.0", "entry": "2.0.0", "manifest": "2.0.0"}
    if plugin_hooks == GENERATED:
        write_hook_source(root)
        write_generated_hooks(root)
    elif plugin_hooks is not None:
        write_json(root / "plugin/hooks/hooks.json", plugin_hooks)
    if include_marketplace:
        write_codex_marketplace(root, marketplace_source_path, include_policy, include_category)
    if not include_manifest:
        return
    write_codex_manifest(root, codex_version, manifest_skills_path, codex_hooks)
    write_claude_files(root, versions, claude_hooks)
    write_cursor_files(root, versions, manifest_skills_path, cursor_hooks)


def make_antigravity_package(root: Path, name: str = "consult") -> None:
    """Write the Antigravity marker plugin/plugin.json."""
    write_json(root / "plugin/plugin.json", {"name": name})


def make_rule_coverage(root: Path, coverage: dict[str, str] | None = None) -> None:
    """Write eval/verifier/rules.json and an empty consult_rules.py check registry."""
    write_json(root / "eval/verifier/rules.json", coverage or {"good.1": "untested"})
    registry = root / "eval/verifier/shared/consult_rules.py"
    registry.parent.mkdir(parents=True, exist_ok=True)
    registry.write_text("CHECKS = {}\n", encoding="utf8")


class ValidatorTestCase(TempDirTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.skills_dir = self.tmp / "agents/.agents/skills"

    def validate(self, *args: str | Path):
        return run([*COMMAND, *(args or [self.skills_dir])])

    def mirror(self, name: str = "good") -> None:
        """Copy a canonical skill into plugin/skills so the mirror is in sync."""
        shutil.copytree(self.skills_dir / name, self.tmp / "plugin/skills" / name)

    def make_good_packaged_repo(self, **package_options: Any) -> None:
        """One good skill, mirrored, with plugin packages built from `package_options`."""
        make_skill(self.skills_dir, "good")
        self.mirror()
        make_plugin_packages(self.tmp, **package_options)
        make_antigravity_package(self.tmp)

    def assert_fails_with(self, result, *texts: str) -> None:
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        for text in texts:
            self.assertIn(text, result.stdout)


class SelfTestAndValidRepoTests(ValidatorTestCase):
    def test_runs_its_self_test_successfully(self) -> None:
        result = self.validate("--self-test")

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(result.stdout.strip(), "self-test ok")

    def test_passes_when_skill_anatomy_and_plugin_mirror_are_valid(self) -> None:
        self.make_good_packaged_repo()
        make_rule_coverage(self.tmp)

        result = self.validate()

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        for text in [
            "all skills conform to the anatomy",
            "plugin/skills mirror in sync with source",
            "codex plugin package valid",
            "cursor plugin package valid",
            "antigravity plugin package valid",
            "plugin hooks valid",
            "rule coverage complete (1 untested)",
        ]:
            self.assertIn(text, result.stdout)
        mirrored = (self.tmp / "plugin/skills/good/SKILL.md").read_text(encoding="utf8")
        self.assertEqual(mirrored, (self.skills_dir / "good/SKILL.md").read_text(encoding="utf8"))


class SkillAnatomyTests(ValidatorTestCase):
    def test_reports_skill_anatomy_findings(self) -> None:
        make_skill(self.skills_dir, "bad", BAD_SKILL)

        self.assert_fails_with(
            self.validate(),
            "bad/SKILL.md",
            "missing section: ## When to Use",
            "missing section: ## Rules",
            "inline 'per <expert>' attribution found",
            "obsolete section: ## Common Rationalizations",
            "obsolete section: ## Red Flags",
            "obsolete table header",
            "1 skill(s) failed anatomy validation",
        )

    def test_measures_a_quoted_description_past_its_first_inner_colon(self) -> None:
        description = (
            "Use for design-partner mode: discovery, tradeoffs, decisions, and the agreed design "
            "artifacts that later implementation work binds itself to."
        )
        body = GOOD_SKILL.replace("description: Good test skill", f'description: "{description}"')
        make_skill(self.skills_dir, "quoted", body)

        self.assert_fails_with(
            self.validate(),
            "quoted/SKILL.md",
            f"frontmatter description too long ({len(description)} > 120 characters)",
        )

    def test_rejects_more_than_eight_tripwire_rows(self) -> None:
        make_skill(self.skills_dir, "long-tripwires", LONG_TRIPWIRES_SKILL)

        self.assert_fails_with(self.validate(), "long-tripwires/SKILL.md", "Tripwires has 9 rows (max 8)")

    def test_rejects_legacy_rule_sections_once_a_skill_has_rules(self) -> None:
        legacy = "## Verification\n\n- [ ] check\n\n## Core Ideas\n\n1. idea\n\n## Workflow"
        make_skill(self.skills_dir, "stale", GOOD_SKILL.replace("## Workflow", legacy))

        self.assert_fails_with(self.validate(), "obsolete section: ## Verification", "obsolete section: ## Core Ideas")

    def test_rejects_a_body_over_the_word_budget(self) -> None:
        padding = " ".join(["word"] * 700)
        make_skill(self.skills_dir, "bloated", f"{GOOD_SKILL}\n{padding}\n")

        result = self.validate()

        self.assertEqual(result.returncode, 1)
        self.assertRegex(result.stdout, r"body too long \(\d+ > 700 words\)")

    def test_rejects_a_model_key_in_skill_frontmatter(self) -> None:
        make_skill(self.skills_dir, "pinned", GOOD_SKILL.replace("name: good\n", "name: pinned\nmodel: haiku\n"))
        mentions = GOOD_SKILL.replace("name: good\n", "name: mentions\n").replace(
            "1. check", "1. check\n\nmodel: in the body is fine."
        )
        make_skill(self.skills_dir, "mentions", mentions)

        result = self.validate()

        self.assert_fails_with(result, "pinned/SKILL.md", "frontmatter sets model")
        self.assertNotIn("mentions/SKILL.md", result.stdout)

    def test_rejects_bullet_format_tripwires_sections(self) -> None:
        head = GOOD_SKILL[: GOOD_SKILL.index("## Tripwires")]
        make_skill(self.skills_dir, "bullets", head + "## Tripwires\n\n- A bullet tripwire.\n")

        self.assert_fails_with(
            self.validate(),
            "bullets/SKILL.md",
            "Tripwires must use the '| Trigger | Do this instead | False alarm |' table format",
        )

    def test_rejects_em_dashes_and_drifted_approval_sentences(self) -> None:
        skill = make_skill(self.skills_dir, "dashy", EM_DASH_SKILL)
        (skill / "references").mkdir()
        (skill / "references/notes.md").write_text("A reference — with an em dash.\n", encoding="utf8")

        self.assert_fails_with(
            self.validate(),
            "dashy/SKILL.md",
            "em dash found -- use a period, colon, comma, or parentheses instead",
            "dashy/references/notes.md",
            "'approving design or RFC' used without the canonical sentence",
        )

    def test_cross_checks_the_workflow_routing_table_against_the_skill_set(self) -> None:
        make_skill(self.skills_dir, "workflow", ROUTER_SKILL)
        make_skill(self.skills_dir, "good")
        make_skill(self.skills_dir, "orphan", GOOD_SKILL.replace("name: good", "name: orphan"))

        self.assert_fails_with(
            self.validate(),
            "workflow/SKILL.md",
            "routing table names 'ghost-skill' but no such skill exists",
            "skill 'orphan' is not referenced by the workflow router",
        )


class PluginPackageTests(ValidatorTestCase):
    def test_reports_plugin_drift_when_a_skill_mirror_is_missing(self) -> None:
        make_skill(self.skills_dir, "good")
        (self.tmp / "plugin/skills").mkdir(parents=True)
        make_plugin_packages(self.tmp)
        make_antigravity_package(self.tmp)

        self.assert_fails_with(
            self.validate(),
            "all skills conform to the anatomy",
            "plugin/skills drift:",
            "plugin/skills/good missing",
            "1 plugin/skills mirror difference(s) found",
        )

    def test_reports_missing_codex_marketplace_when_plugin_exists(self) -> None:
        self.make_good_packaged_repo(include_marketplace=False)

        self.assert_fails_with(self.validate(), "codex plugin:", "missing", ".agents/plugins/marketplace.json")

    def test_reports_invalid_codex_marketplace_and_manifest_fields(self) -> None:
        self.make_good_packaged_repo(
            marketplace_source_path="./wrong",
            include_policy=False,
            include_category=False,
            manifest_skills_path="./wrong/",
            codex_hooks=True,
        )

        self.assert_fails_with(
            self.validate(),
            "consult.source.path must be './plugin'",
            "consult.policy must be an object",
            "consult.category must be 'Coding'",
            "skills must be './skills/'",
            "must not declare hooks",
        )

    def test_reports_hook_declarations_in_plugin_manifests(self) -> None:
        self.make_good_packaged_repo(codex_hooks=True, claude_hooks=True, cursor_hooks=True)

        self.assert_fails_with(
            self.validate(),
            "plugin/.codex-plugin/plugin.json must not declare hooks",
            "plugin/.claude-plugin/plugin.json must not declare hooks",
            "plugin/.cursor-plugin/plugin.json must not declare hooks",
        )

    def test_reports_a_plugin_hooks_file_with_one_problem(self) -> None:
        def session_start(handler: dict[str, Any]) -> dict[str, Any]:
            return {"SessionStart": [{"hooks": [handler]}]}

        cases = [
            ("is missing", None, "missing"),
            (
                "declares a second event",
                {"hooks": {**session_start({"type": "command", "command": "echo hi"}), "PreToolUse": []}},
                "declares SessionStart, PreToolUse; Consult ships exactly one SessionStart command hook",
            ),
            (
                "uses a non-command handler",
                {"hooks": session_start({"type": "prompt", "prompt": "load workflow"})},
                "SessionStart handler must be { type: 'command', command: <non-empty string> }",
            ),
        ]
        for label, plugin_hooks, message in cases:
            with self.subTest(label):
                shutil.rmtree(self.tmp / "agents", ignore_errors=True)
                shutil.rmtree(self.tmp / "plugin", ignore_errors=True)
                self.make_good_packaged_repo(plugin_hooks=plugin_hooks)

                self.assert_fails_with(self.validate(), "1 plugin hook problem(s)", message)

    def test_reports_a_hooks_file_that_no_longer_matches_its_core_md_source(self) -> None:
        self.make_good_packaged_repo()
        write_hook_source(self.tmp, "Consult is installed. Edited after generation.\n")

        self.assert_fails_with(
            self.validate(),
            "1 plugin hook problem(s)",
            f"plugin/hooks/hooks.json differs from {HOOK_SOURCE}",
        )

    def test_requires_a_rules_json_entry_for_each_numbered_core_md_rule(self) -> None:
        self.make_good_packaged_repo()
        core = "Consult is installed. Load the consult:workflow skill.\n\n## Rules\n\n1. One.\n2. Two.\n"
        write_hook_source(self.tmp, core)
        write_generated_hooks(self.tmp, core)
        make_rule_coverage(self.tmp, {"good.1": "untested", "core.1": "untested", "core.3": "untested"})

        result = self.validate()

        self.assert_fails_with(
            result,
            "plugin hooks valid",
            "rule core.2 has no entry in rules.json",
            "rules.json names core.3, which is not a rule in its SKILL.md or core.md",
        )
        self.assertNotIn("rule core.1 has no entry", result.stdout)

    def test_reports_a_hooks_file_whose_core_md_source_is_missing(self) -> None:
        self.make_good_packaged_repo()
        (self.tmp / HOOK_SOURCE).unlink()
        (self.tmp / HOOK_SOURCE.replace("agents/.agents/skills/", "plugin/skills/")).unlink()

        self.assert_fails_with(self.validate(), f"missing {HOOK_SOURCE}, the source of plugin/hooks/hooks.json")

    def test_reports_plugin_version_drift_across_claude_and_codex_manifests(self) -> None:
        self.make_good_packaged_repo(
            codex_version="2.0.0",
            claude_versions={"marketplace": "2.1.0", "entry": "2.2.0", "manifest": "2.3.0"},
        )

        self.assert_fails_with(
            self.validate(),
            "version must match",
            "consult.version must match metadata.version",
            "plugin/.codex-plugin/plugin.json",
            "plugin/.claude-plugin/plugin.json",
            "plugin/.cursor-plugin/plugin.json",
        )

    def test_reports_invalid_cursor_marketplace_and_manifest_fields(self) -> None:
        self.make_good_packaged_repo(manifest_skills_path="./wrong/")
        marketplace = {
            "name": "consult",
            "owner": {"name": "Dawson Design Ltd."},
            "metadata": {"version": "2.0.0"},
            "plugins": [{"name": "consult", "version": "2.0.0", "source": "./wrong"}],
        }
        write_json(self.tmp / ".cursor-plugin/marketplace.json", marketplace)
        write_json(
            self.tmp / "plugin/.cursor-plugin/plugin.json",
            {"name": "consult", "version": "2.0.0", "skills": "./wrong/"},
        )

        self.assert_fails_with(
            self.validate(),
            ".cursor-plugin/marketplace.json consult.source must be './plugin'",
            "plugin/.cursor-plugin/plugin.json skills must be './skills/'",
        )

    def test_reports_invalid_google_antigravity_plugin_fields(self) -> None:
        self.make_good_packaged_repo()
        make_antigravity_package(self.tmp, name="wrong")

        self.assert_fails_with(self.validate(), "antigravity plugin:", "plugin/plugin.json name must be 'consult'")


if __name__ == "__main__":
    unittest.main()
