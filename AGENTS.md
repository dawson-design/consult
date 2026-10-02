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
repo maintenance helpers, plugin packaging, and extension packages.

## Source of truth and mirrors

- **Canonical skills**: `agents/.agents/skills/<name>/SKILL.md`. Every skill
  lives here; siblings may add `agents/`, `references/`, and `scripts/`.
- **Repo instructions**: `AGENTS.md` is the main portable instruction file in
  the repo. `CLAUDE.md` mirrors the same maintainer guidance for hosts that read
  Claude-specific files. Normal Consult use relies on skill frontmatter, plugin
  metadata, the `workflow` skill, and the plugin SessionStart hook that tells
  the agent to load `workflow` before non-trivial code work; users do not need
  to install or merge system instruction files.
- **Claude Code plugin mirror**: `plugin/skills/<name>` contains generated
  copies of canonical skills from `agents/.agents/skills/<name>`.
  `.claude-plugin/marketplace.json` points Claude Code at the `plugin/` root,
  where `plugin/.claude-plugin/plugin.json` exposes namespaced
  `/consult:<skill>` slash commands.
- **Codex plugin package**: `.agents/plugins/marketplace.json` points Codex at
  the `plugin/` root, and `plugin/.codex-plugin/plugin.json` exposes the same
  generated skill mirror to Codex as a plugin. Keep the Codex marketplace and
  manifest in sync with Claude plugin packaging.
- **Plugin SessionStart hook**: `plugin/hooks/hooks.json` is hand-written, not
  generated. Claude Code and Codex discover it by convention, so no manifest
  declares `hooks`. It holds exactly one SessionStart command that prints the
  routing line, and the validator rejects anything more. Codex runs it only
  after the user trusts it. Cursor and Antigravity also find the file:
  Antigravity cannot parse the Claude Code format and still loads the skills,
  and whether Cursor uses the plain-text output is unverified.
- **Cursor plugin package**: `.cursor-plugin/marketplace.json` points Cursor at
  the `plugin/` root, and `plugin/.cursor-plugin/plugin.json` exposes the same
  generated skill mirror as a Cursor plugin whose manifest declares no hooks or
  MCP. Keep the Cursor
  marketplace and manifest in sync with Claude plugin packaging.
- **Google Antigravity plugin package**: `plugin/plugin.json` is the
  Antigravity marker for Consult. Local installs create an Antigravity plugin
  directory that links only `plugin/plugin.json` and the generated
  `plugin/skills/` mirror under `~/.gemini/config/plugins/consult`.
- **Install layout**: `agents/` is a GNU Stow package. `./setup.sh` is the
  one-click local installer: it explains the actions, asks for approval, runs
  Stow to link the shared skills under `~/.agents/`, fans those out to
  per-tool locations, prunes manual Codex links when the Consult Codex plugin is
  installed, and re-runs the plugin-sync. System `AGENTS.md` / `CLAUDE.md`
  files are not part of Consult installation.

When you add, rename, or delete a skill, the canonical file under
`agents/.agents/skills/` is the only place to write. Everything else is
regenerated.

## Pi self-improvement source access

Pi can inspect its own installed package when runtime behavior, extension APIs,
or self-improvement work depends on Pi internals. Treat that package as a
read-only upstream source: read it to confirm current APIs and behavior, but
make Consult changes in this repository unless the user explicitly asks to work
on Pi itself.

For most npm-style installs, find Pi's package with:

```sh
npm root -g
```

Then look under `@earendil-works/pi-coding-agent` in that global
`node_modules` directory. Package-manager installs usually place the same global
`node_modules` tree under the manager prefix, for example
`<prefix>/lib/node_modules/@earendil-works/pi-coding-agent`. Do not hard-code a
machine-specific absolute path in repo docs or committed code. Resolve it at
runtime with `npm root -g`, `which pi`, or the package manager's prefix command.

Useful read-only entry points are the package `README.md`, `docs/`, `examples/`,
`package.json`, and exported type declarations. Follow linked docs before
changing Consult extensions that depend on Pi APIs.

## Host posture: attended vs unattended

Consult targets two different working modes, and that difference decides where
enforcement is allowed to live. It is a deliberate split, not an inconsistency
or a gap in coverage.

- **Attended hosts (Claude Code, Codex, Cursor, and the rest).** A human is
  watching the session and answering as it runs. The human *is* the gate, so
  skills carry high-level guidance and ask for sign-off in prose. Consultation
  works here because someone is present to consult.
- **Unattended host (Pi).** Nobody is reading the session while it runs, so a
  prose request for approval has no one to answer it. Pi therefore gets runtime
  enforcement — `consult/extensions/self-review-guard.ts` and the `/proof`
  command — that mechanically holds the line a present human would otherwise
  hold.

Consequences for anyone editing this repo:

- Do not "fix" the attended hosts by adding host-specific enforcement
  primitives, blocking gates, or hook configuration to shared skill bodies. The
  absence of those is the design. Skill prose stays portable and host-neutral.
- Do not move Pi's enforcement into skill prose either. Runtime gates belong in
  `consult/extensions/`, where they apply only to the host that needs them.
- The plugin SessionStart hook is context, not enforcement. It prints one
  routing line and blocks nothing. Keep it that way: a hook that gates or
  checks work is the host-specific enforcement the attended hosts leave out.
- When a skill body says to get approval, it is addressing an attended session.
  Keep that phrasing about the *decision* that needs a human, not about the
  mechanism a particular host would use to block on it.

## Common commands

A clean clone installs with `pnpm install`. `eval/` is a separate `uv` project
that runs the Consult evaluation suite through Harbor; it is not a pnpm
workspace package. `make eval` runs its static checks and `make smoke` runs
one real trial. See `eval/README.md` for setup.

`make test` runs the whole check sequence, cheapest first, so a failing test
suite cannot stop the anatomy validator from reporting. `.github/workflows/ci.yml`
runs the same checks as separate steps on every push and pull request.

```sh
# Re-run the local installer and per-tool fan-out after a
# skill is added / renamed / removed. Idempotent.
./setup.sh

# Refresh the generated plugin skill mirror.
node scripts/generate-plugin-symlinks.mjs

# Validate every SKILL.md against the playbook anatomy (frontmatter,
# required sections, no inline expert attribution), plugin/ drift, and
# Codex and Google Antigravity plugin shapes. Run this before publishing
# skill changes.
node scripts/validate-skill-anatomy.mjs

# Validate local Markdown links and anchors. Remote URL checks are omitted by
# default so this stays deterministic for local development.
pnpm run check:links

# Self-test the validator itself (uses a tmp dir of fixtures).
node scripts/validate-skill-anatomy.mjs --self-test

# Repo-owned tests.
pnpm test
```

There is no product application test suite; repo-level Vitest, the anatomy
validator, and `check:links` are maintenance checks. Treat clean Vitest,
`validate-skill-anatomy.mjs`, and `check:links` commands as the bar for script
changes.

## Maintainer skills

- `$ship` is a project-local Codex skill for the guarded maintainer ship flow.
  Its source lives at `.agents/skills/ship/SKILL.md`. It is not part of the
  published Consult skill pack. Do not move it into `plugin/skills/` or bump
  plugin package versions for changes to this skill alone. Current Codex CLI
  builds do not support repo-local custom slash commands, so `/ship` is not the
  supported invocation path.

## Validation scope and token discipline

Run the narrowest check that proves the touched surface first. Broaden only
when the changed files require it or the narrow check exposes cross-package
risk.

- Pi runtime extension changes under `consult/extensions/` or
  `consult/test/`: run `pnpm --dir consult test`.
- Canonical skill prose changes: run `node scripts/validate-skill-anatomy.mjs`.
  It now checks every generated mirror (`plugin/skills` and `consult/skills`,
  read from the generator's `MIRROR_DESTS`), so it is sufficient on its own — no
  separate `cmp` pass, and no need for root `pnpm test`. Regenerate with
  `node scripts/generate-plugin-symlinks.mjs` when it reports drift.
- Markdown link/doc-wide changes: run `pnpm run check:links` only when
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
  routing surface and leaves room for roughly four more skills; it was raised
  from 2,000 once the validator stopped truncating descriptions at their first
  inner colon and revealed the pack had been over the old limit all along. Raise
  it again only with a stated reason.
- Required sections: `## When to Use`, `## When NOT to Use`, `## Rules`.
- Body budget: 700 words after frontmatter. Raised for three skills, each
  with a reason recorded next to the constant: 950 for `proof` and
  `code-review` and 1,120 for `workflow`, which carry the routing and sign-off
  tables plus the host-harness, fresh-context-review, and plan-handoff
  policy. Table pipes
  and separator rows do not count. Raise a skill's budget only with a stated
  reason. The budget is the regression guard for the knowledge-vs-policy
  rule below. Raise a single skill's budget only with a stated reason.
- Optional section: `## Tripwires` when a skill has known agent failure modes.
  Table format only, at most 8 rows. Use them only for high-probability
  moments where agents weaken, skip, or misapply the skill. Put rare
  exceptions and detailed taxonomies in references. Omit the section when no
  row pays for its tokens.
- No inline `per <Expert Name>` attribution outside a `## References` or
  `## Canon` section: move citations there.
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

Each rule is stated once. Section ownership:

- `## When to Use`: routing triggers only. Say when to load the skill.
- `## When NOT to Use`: routing exclusions and handoffs only. Say which
  neighboring skill owns the work instead.
- `## Iron Law`: one non-negotiable rule, only when the skill has one.
- `## Rules`: the single statement of each policy rule, numbered, in checkable
  form. Named sub-sections are fine for reusable contracts (the Proof
  Contract, the Independent Review block). No ordered steps, no examples that
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

Plus the README's authoring rules: keep skills short and directive. A
`SKILL.md` is steering context, not a book: every paragraph competes with the
repo, diff, user request, and proof evidence for the agent's attention. The
body should answer only when to use the skill, what rule/workflow to follow,
and how to verify the result. Lead with an Iron Law when one exists, route to
neighbours via `Handoffs` instead of duplicating their bodies, push
deterministic checks into `scripts/`, and move nuance, citations, examples, and
deep ecosystem notes into targeted `references/` files that are loaded only
when needed.

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

Adding or renaming a skill needs four updates, in order:

1. Canonical files under `agents/.agents/skills/<name>/` (and a test that
   the body satisfies the validator's required sections).
2. `README.md`: update the human-facing skill list and its
   `[skill-<name>]:` reference link at the bottom.
3. `workflow`: update the meta-skill only when the new or renamed skill changes
   the broad Consult routing workflow.
4. `./setup.sh` to regenerate `plugin/skills/<name>` and refresh or prune
   per-agent manual-install links. The validator's drift check fails CI/local
   runs if step 4 is skipped.

Neighbouring skills may need their `Handoffs` updated when routing
changes. Do not duplicate skill prose between files.

## Pack versioning (`marketplace.json` / `plugin.json`)

The pack publishes a single semantic version in
`.claude-plugin/marketplace.json` (both `metadata.version` and the
`plugins[0].version`), `.cursor-plugin/marketplace.json` (same fields),
`plugin/.claude-plugin/plugin.json`, `plugin/.cursor-plugin/plugin.json`, and
`plugin/.codex-plugin/plugin.json`. Bump all of them together when canonical
content changes so plugin managers see the same package version.

| Bump | Trigger |
|---|---|
| **major** (X.0.0) | Skill renamed or removed; an Iron Law or non-negotiable rule reversed; anything that changes what agents will refuse vs accept |
| **minor** (1.X.0) | New skill added; new reference file under `references/`; new section in an existing `SKILL.md`; doctrine clarified or strengthened without reversal; new tooling expectation that's strictly additive |
| **patch** (1.0.X) | Typos, link fixes, formatting, internal re-flow that doesn't change meaning |

Bump in the same PR as the canonical edit; both `version` fields move
together. Pre-1.0 (`0.x.y`) is reserved for early development and
follows the same shape, but minor bumps may carry breaking changes;
the pack is past that and should not regress to it.

## Conventions specific to this repo

- Markdown, JavaScript, and TypeScript are the repo-owned languages. Use
  Vitest for repo-owned JS/TS tests and `check:links` for local Markdown link
  validation. Keep Markdown prose manually formatted; do not add a docs
  formatter.
- Pi extension source must be TypeScript, not JavaScript. Use `.ts` for
  repo-local `.pi/extensions/` commands and packaged
  `consult/extensions/` runtime extensions; keep generated,
  third-party, or ordinary maintenance scripts in their existing language
  unless the task is explicitly to migrate them.
- Do not add author-attribution trailers (`Co-Authored-By`,
  `Generated by`) to commits.
