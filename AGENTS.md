# AGENTS.md

This file provides guidance to coding agents (Claude Code, Codex, Cursor, and
others that read `AGENTS.md`) when working with code in this repository.

## What this repo is

Consult is a portable skill pack for coding agents (Claude Code,
Codex, Cursor, Copilot, Gemini CLI, Google Antigravity, OpenCode, Pi,
Windsurf). It ships
prose (`SKILL.md` files plus a few maintenance helpers), not application code.
Most edits are to skill bodies, the top-level `AGENTS.md`, or the
`README.md`. There is no application build or service to run; tests cover
repo maintenance helpers and plugin packaging.

Claude Code is the primary host: the maintainer and their workplace use it,
so design for how Claude Code works and check behavior changes there first.
Codex must keep working, and the eval measures both. The other hosts load the
same skills, but nothing measures them, and Claude Code mechanisms such as
the SessionStart hook are acceptable even where those hosts lack them.

## Source of truth and mirrors

- **Canonical skills**: `agents/.agents/skills/<name>/SKILL.md`. Every skill
  lives here; siblings may add `agents/`, `references/`, and `scripts/`.
- **Repo instructions**: `AGENTS.md` is the main portable instruction file in
  the repo. `CLAUDE.md` imports it with `@AGENTS.md`, because Claude Code reads
  `CLAUDE.md` but not `AGENTS.md`. Normal Consult use relies on skill
  frontmatter, plugin metadata, the `workflow` skill, and the plugin
  SessionStart hook, which prints the Consult core (always-on rules) and
  tells the agent to load `workflow` before non-trivial code work; users do
  not need to install or merge system instruction files.
- **Claude Code plugin mirror**: `plugin/skills/<name>` contains generated
  copies of canonical skills from `agents/.agents/skills/<name>`.
  `.claude-plugin/marketplace.json` points Claude Code at the `plugin/` root,
  where `plugin/.claude-plugin/plugin.json` exposes namespaced
  `/consult:<skill>` slash commands.
- **Codex plugin package**: `.agents/plugins/marketplace.json` points Codex at
  the `plugin/` root, and `plugin/.codex-plugin/plugin.json` exposes the same
  generated skill mirror to Codex as a plugin. Keep the Codex marketplace and
  manifest in sync with Claude plugin packaging.
- **Plugin SessionStart hook**: `plugin/hooks/hooks.json` is generated from
  `agents/.agents/skills/workflow/references/core.md` by
  `scripts/generate_plugin_symlinks.py`. Edit `core.md`, never
  `hooks.json`. Claude Code and Codex discover it by convention, so no
  manifest declares `hooks`. It holds exactly one SessionStart command, a
  heredoc that needs a POSIX `sh`, which prints `core.md` inline. The
  validator rejects anything more, and any drift from `core.md`. Codex runs
  it only after the user trusts it. Cursor and Antigravity also find the file:
  Antigravity cannot parse the Claude Code format and still loads the skills,
  and whether Cursor uses the plain-text output is unverified.
- **Cursor plugin package**: `.cursor-plugin/marketplace.json` points Cursor at
  the `plugin/` root, and `plugin/.cursor-plugin/plugin.json` exposes the same
  generated skill mirror as a Cursor plugin whose manifest declares no hooks or
  MCP. Keep the Cursor
  marketplace and manifest in sync with Claude plugin packaging.
- **Google Antigravity plugin package**: `plugin/plugin.json` is the
  Antigravity marker for Consult. Local installs run
  `agy plugin install <repo>/plugin`, which copies the generated
  `plugin/skills/` mirror into `~/.gemini/antigravity-cli/plugins/consult`.
  The copy goes stale until the command runs again.
- **Install layout**: `agents/` is a GNU Stow package. `./setup.sh` is the
  one-click local installer: it explains the actions, asks for approval, runs
  Stow to link the shared skills under `~/.agents/`, fans those out to
  per-tool locations, prunes manual Codex links when the Consult Codex plugin is
  installed, and re-runs the plugin-sync. System `AGENTS.md` / `CLAUDE.md`
  files are not part of Consult installation.

When you add, rename, or delete a skill, the canonical file under
`agents/.agents/skills/` is the only place to write. Everything else is
regenerated.

## Host posture: attended sessions

Consult assumes a person is watching the session and answering as it runs.
That person *is* the gate, so skills carry high-level guidance and ask for
sign-off in prose. Consultation works because someone is present to consult.
Consult ships no runtime enforcement. A run with nobody to answer (headless,
scheduled, or delegated) stops at each sign-off gate and reports what needs
approval. A delegated subagent hands the question back to its parent.

Consequences for anyone editing this repo:

- Do not add host-specific enforcement primitives, blocking gates, or hook
  configuration to shared skill bodies. The absence of those is the design.
  Skill prose stays portable and host-neutral.
- The plugin SessionStart hook is context, not enforcement. It prints the
  Consult core (`workflow/references/core.md`) and blocks nothing. Keep it
  that way: a hook that gates or checks work is the host-specific
  enforcement Consult leaves out.
- When a skill body says to get approval, it is addressing the person in the
  session. Keep that phrasing about the *decision* that needs a human, not
  about the mechanism a particular host would use to block on it.

## Common commands

The maintainer checks need `python3` 3.12 or newer, `uv`, and `lychee`
(`brew install lychee`). The root `pyproject.toml` pins ruff, the only Python
dev dependency, and `uv run` installs it on first use. `eval/` is a separate
`uv` project that runs the Consult evaluation suite through Harbor. `make eval`
runs its static checks and `make smoke` runs one real trial. See
`eval/README.md` for setup.

Real eval runs (`make smoke`, `make eval-fast`, `make eval-triggers`, and
`eval/scripts/run.py`) bill the maintainer's Claude or Codex subscription.
Start one only when the maintainer asks, and state the trial count first.

`make test` runs the whole check sequence, cheapest first, so a failing test
suite cannot stop the anatomy validator from reporting. `.github/workflows/ci.yml`
runs the same checks as separate steps on every push and pull request, plus the
eval verifier sync and rule-check tests.

```sh
# Re-run the local installer and per-tool fan-out after a
# skill is added / renamed / removed. Idempotent.
./setup.sh

# Refresh the generated plugin skill mirror and SessionStart hook.
python3 scripts/generate_plugin_symlinks.py

# Validate every SKILL.md against the playbook anatomy (frontmatter,
# sections, budgets, em dashes, attribution), plugin/ drift, rule coverage
# in eval/verifier/rules.json, the plugin hooks file, and the Codex, Cursor,
# and Google Antigravity plugin packages. Run this before publishing skill
# changes.
python3 scripts/validate_skill_anatomy.py

# Validate local Markdown links and anchors with lychee. Remote URLs are
# skipped so this stays deterministic for local development.
make links

# Self-test the validator itself (uses a tmp dir of fixtures).
python3 scripts/validate_skill_anatomy.py --self-test

# ruff lint and format check over every repo-owned Python file.
make lint

# Repo-owned tests.
python3 -m unittest discover -s tests
```

There is no product application test suite; the repo's unittest suite, the
anatomy validator, `make lint`, and `make links` are maintenance checks.
Treat them passing as the bar for script changes.

## Maintainer skills

- `ship` is a project-local skill for the guarded maintainer ship flow. Its
  source lives at `.agents/skills/ship/SKILL.md`. Codex invokes it as `$ship`,
  because current Codex CLI builds do not support repo-local slash commands;
  Claude Code lists it as the `ship` skill. It is not part of the published
  Consult skill pack. Do not move it into `plugin/skills/` or bump plugin
  package versions for changes to this skill alone.

## Validation scope and token discipline

Run the narrowest check that proves the touched surface first. Broaden only
when the changed files require it or the narrow check exposes cross-package
risk.

- Canonical skill prose changes: run `python3 scripts/validate_skill_anatomy.py`.
  It checks the generated mirror (`plugin/skills`, read from the
  generator's `MIRROR_DESTS`), so it is sufficient on its own; no
  separate `cmp` pass, and no need for the repo test suite. Regenerate with
  `python3 scripts/generate_plugin_symlinks.py` when it reports drift.
- `eval/` changes: run `make eval`, which needs `harbor` and `uv`, or the two
  checks CI runs without them: `python3 eval/scripts/sync_tests.py --check`
  and `python3 -m unittest discover eval/verifier/tests`.
- Markdown link/doc-wide changes: run `make links` only when
  links or broad docs moved. Do not run it for ordinary runtime or narrow skill
  edits.
- Release/package metadata changes: run the release/package checks that match
  the edited manifests, locks, or plugin metadata. Do not treat implementation
  approval as approval to add release-prep edits.
- After compaction, re-read only the files needed for the current slice.
  Avoid replaying long session history,
  broad diffs, or full validators to rebuild context unless the next action
  depends on them.

If a command prints hundreds of lines, stop repeating it. Summarize the failed
check and switch to a narrower command or exact file inspection.

## Skill anatomy (enforced by the validator)

Every `SKILL.md` must have:

- Frontmatter with kebab-case `name:` and a trigger-focused `description:`
  no longer than 120 characters, and the pack-wide canonical description total
  must stay under 2,400 characters, because agents may load every description
  before selecting a skill body. That ceiling is ~600 tokens of always-loaded
  routing surface. With `issue-tracking` the pack sits at 2,399, so the next
  skill needs description cuts elsewhere. The ceiling was raised from 2,000
  once the validator stopped truncating descriptions at their first inner
  colon and revealed the pack had been over the old limit all along. Raise it
  again only with a stated reason.
- No `model:` key in frontmatter. A skill that names a model makes the host
  switch models when it loads, which throws away the prompt cache.
- Required sections: `## When to Use`, `## When NOT to Use`, `## Rules`.
- Body budget: 700 words after frontmatter. Raised for four skills, each with
  a reason recorded next to the constant: 730 for `api`, whose REST
  compatibility rules are written as plain sentences; 950 for `code-review`,
  1,050 for `proof`, and 943 for `workflow`, which carry the routing table
  and sign-off list plus the fresh-context-review, plan-handoff,
  delegated-model, build-stage, test-level, and test-oracle policy. Table
  pipes and separator rows do not count. The budget is the regression guard for the
  knowledge-vs-policy rule below. Raise a single skill's budget only with a
  stated reason.
- Optional section: `## Tripwires` when a skill has known agent failure modes.
  Table format only, at most 8 rows, with this header:
  `| Trigger | Do this instead | False alarm |`. Use them only for
  high-probability moments where agents weaken, skip, or misapply the skill.
  Put rare exceptions and detailed taxonomies in references. Omit the section
  when no row pays for its tokens.
- No inline `per <Expert Name>` attribution outside a `## References` or
  `## Canon` section: move citations there.
- No em dashes in a skill body or its `references/` files. Use a period,
  colon, comma, or parentheses.
- A skill that mentions approving a design or RFC carries this sentence
  verbatim, so the rule cannot drift between skills: "An approving design or
  RFC approves the direction, not the concrete shapes".
- Put references to people, books, talks, papers, videos, and YouTube links in
  `## References`, `## Canon`, or a `references/` file, not in frontmatter or
  the steering body. Skill bodies should spend tokens on agent behavior, not
  provenance.

Knowledge versus policy. A current frontier model already applies standard
engineering practice unprompted. A sentence earns its place in a skill body
only if it is one of:

1. Policy: a rule this pack wants that the model would not pick on its own
   (sign-off gates, thresholds, house defaults, what counts as done).
2. Tripwire: a pressure phrase paired with the corrective action and a
   false-alarm escape.
3. Philosophy: Simple Made Easy, data/calculations/actions, functional core,
   contract-first, illegal states unrepresentable.
4. Routing: when to load, when not, handoffs, reference load triggers.

Delete anything that teaches standard practice. Where a rule is non-obvious to
a junior engineer, keep one short "because" clause, not a paragraph.

Core and workflow scope. `workflow/references/core.md` is the Consult core:
the plugin's SessionStart hook prints it into every session, so it holds the
rules every code change needs, such as core rule 5's code-shape thresholds,
whether or not a skill loads. Its numbered rules have eval ids `core.<n>`.
`workflow` loads on non-trivial code tasks, so it holds the gates, the
process, and routing to the other skills. Process detail for narrower
situations goes to the skill that owns it, or to a `workflow/references/`
file that workflow's References section says when to load. Gate rules that
eval checks or other skills cite (Rule 2's approval list, Rule 4's stage
sign-off) stay in the workflow body.

Each rule is stated once. Section ownership:

- `## When to Use`: routing triggers only. Say when to load the skill.
- `## When NOT to Use`: routing exclusions and handoffs only. Say which
  neighboring skill owns the work instead.
- `## Iron Law`: one non-negotiable rule, only when the skill has one.
- `## Rules`: the single statement of each policy rule, numbered, in checkable
  form. Named sub-sections are fine for reusable contracts (the Independent
  Review block). No ordered steps, no examples that
  belong in references. Each rule's number is its eval id (`api.1`), so adding,
  removing, or renumbering a rule means updating `eval/verifier/rules.json`;
  the validator fails until you do.
- `## Workflow`: ordered actions, only when ordering itself is the policy.
  Apply the Rules without restating them.
- `## Tripwires`: short positive corrective actions for high-probability
  failure moments where agents skip, weaken, or misapply the skill.
- `## Handoffs`: route unresolved neighboring concerns in one line each. Do
  not summarize the neighbor skill's body.
- `## References` / `## Canon`: citations, deeper examples, recipes, and
  ecosystem detail. Every entry names when to load it.

`## Core Ideas`, `## Verification`, and `## Before Saying Done` are retired.
The validator rejects them once a skill has `## Rules`.

Keep skills short and directive. A `SKILL.md` is steering context, not a book:
every paragraph competes with the repo, diff, user request, and proof evidence
for the agent's attention. The body should answer only when to use the skill,
what rule/workflow to follow, and how to verify the result. Lead with an Iron
Law when one exists, route to neighbours via `Handoffs` instead of duplicating
their bodies, push deterministic checks into `scripts/`, and move nuance,
citations, examples, and deep ecosystem notes into targeted `references/` files
that are loaded only when needed.

Write skill prose in short, plain sentences. Prefer concrete verbs and familiar
words. If a sentence needs rereading, split it. If a heading names an abstract
process, rewrite it as the action the agent should take. Do not use ornate or
literary phrasing when direct engineering language will do.

For `agents/.agents/skills/code-review/references/<language>.md`, do not
duplicate anything a linter, formatter, type checker, syntax checker, or
compiler already catches. Those files should focus on high-signal review risks:
semantic bugs, unsafe edge cases, framework traps, missing proof, and patterns
that automated tooling routinely misses. Make language advice conditional on
the repo's declared runtime, framework, and compatibility policy; never suggest
syntax or libraries that would break supported versions. When naming testing
expectations, steer toward the ecosystem's behavior/spec-flavored test library
when one is available, such as RSpec for Ruby or Vitest/Jest `describe`/`it`
suites for TypeScript, because review evidence should describe caller-visible
behavior.

## When skill changes ripple

Adding or renaming a skill needs five updates, in order:

1. Canonical files under `agents/.agents/skills/<name>/`: `SKILL.md`, and
   `agents/openai.yaml` with the Codex display name, short description, and
   default prompt. Nothing validates `openai.yaml`, so copy a neighbour's
   shape. A new description must fit the pack-wide description ceiling.
2. `eval/verifier/rules.json`: one entry per numbered rule (`<name>.<n>`,
   or `core.<n>` for a rule in `workflow/references/core.md`)
   with status `check`, `judge-only`, or `untested`. The validator fails until
   every rule has one and no entry names a missing rule.
3. `README.md`: add or rename the skill in the grouped list under `## Skills`.
4. `workflow`: update the meta-skill only when the new or renamed skill changes
   the broad Consult routing workflow.
5. `./setup.sh` to regenerate `plugin/skills/<name>` and refresh or prune
   per-agent manual-install links. The validator's drift check fails CI/local
   runs if step 5 is skipped.

Neighbouring skills may need their `Handoffs` updated when routing
changes. Do not duplicate skill prose between files.

## Pack versioning (`marketplace.json` / `plugin.json`)

The pack publishes a single semantic version in
`.claude-plugin/marketplace.json` (both `metadata.version` and the
`plugins[0].version`), `.cursor-plugin/marketplace.json` (same fields),
`plugin/.claude-plugin/plugin.json`, `plugin/.cursor-plugin/plugin.json`,
`plugin/.codex-plugin/plugin.json`, and `plugin/plugin.json` (Antigravity).
They move together so plugin managers see the same package version. The
validator checks all of them except `plugin/plugin.json`.

Feature and fix commits describe their change under `## [Unreleased]` in
`CHANGELOG.md` and leave the versions alone. A release is a separate
`Release X.Y.Z` commit on `main`: it promotes `## [Unreleased]` to a dated
`## [X.Y.Z] (YYYY-MM-DD)` section, leaves a fresh empty `## [Unreleased]`
above it, and bumps every manifest. The `ship` skill runs this flow. Classify
the bump from everything since the last release:

| Bump | Trigger |
|---|---|
| **major** (X.0.0) | Skill renamed or removed; an Iron Law or non-negotiable rule reversed; anything that changes what agents will refuse vs accept |
| **minor** (1.X.0) | New skill added; new reference file under `references/`; new section in an existing `SKILL.md`; doctrine clarified or strengthened without reversal; new tooling expectation that's strictly additive |
| **patch** (1.0.X) | Typos, link fixes, formatting, internal re-flow that doesn't change meaning |

Pre-1.0 (`0.x.y`) is reserved for early development and follows the same
shape, but minor bumps may carry breaking changes; the pack is past that and
should not regress to it.

## Conventions specific to this repo

- Markdown and Python are the repo-owned languages. JavaScript appears only as
  eval content: the hidden checks and task fixtures. `scripts/` and `tests/`
  use only the Python standard library, so they run with a bare `python3`.
  Use `unittest` for tests, ruff (`make lint`) for Python lint and format, and
  `make links` for local Markdown link validation. Keep Markdown prose
  manually formatted; do not add a docs formatter.
- Do not add author-attribution trailers (`Co-Authored-By`,
  `Generated by`) to commits.
