# Consult

Drawn from 25 years of software engineering across startups and large
organizations, Consult is a human in the loop focused portable skill library for
raising the engineering maturity of coding agents.

Humans are good at mapping real-world issues to technical solutions, and, given enough context,
coding agents are good at generating a correct implementation. Consult does not try to
change either side of that equation: it does not automate humans away, and it
does not change how coding agents, or their harnesses, work internally. Instead, it
augments the collaboration between them so agent-assisted work produces simpler,
trustworthy, and maintainable production-grade software while humans still own
intent, design, and acceptance.

Consult is not a vibe-coding safety net. It works best when you have
enough software fundamentals to judge plans, tradeoffs, risk, and proof. Consult can
still suggest a solution, but it's more effective if you can make the hard
engineering decisions yourself (plus you'll actually know how the code works).

## What Consult guides agents to do

- Keep humans in the loop for significant and hard-to-change work: public
  interfaces, project structure, dependency picks, data boundaries, long-lived
  behavior, substantial new modules, non-trivial logic, and deliberate behavior
  changes.
- Use AI to improve the developer's mental model, not to replace it.
- Model data first: make values, states, and rules clear; limit side effects;
  keep state changes at the edges.
- Show their work: prove behavior with tests, contracts, logs, or visible
  checks rather than relying on what seems correct.
- Treat security, data safety, and accessibility as essential, not extras.
- Plan beyond launch: invest in observability, reliability, safe deployment,
  and a rollback plan.
- Organize work into clear, reviewable changes humans can trust and maintain.

## Ceremony scales with stakes

Consult is not a fixed approval pipeline. The `workflow` skill classifies each
task by significance (how much other code it impacts) and durability (how
costly it is to reverse), then sets the involvement level from those stakes.
Low-stakes, disposable work runs autonomously with no gates. Approval gates
fire only when the output is significant or hard to change, and each gate asks
one decision question, not a barrage. If Consult feels like it is asking too
often on routine work, that is a bug: the eval suite lowers a trial's score for
each agent message that ends in a question, and reports of gate fatigue are
worth filing.

## Install

Most users should install the package for their primary agent. Use the manual
install only when you want one shared skill directory across several tools, or
when your tool does not support plugins.

### Claude Code

Inside Claude Code:

```text
/plugin marketplace add kreek/consult
/plugin install consult@consult
```

Prefer the plugin over `./setup.sh` on Claude Code. The plugin namespaces
skills as `/consult:<skill>`, which keeps them distinct from Claude Code's
built-in skills; `setup.sh` symlinks `~/.claude/skills` and registers bare
names, so `code-review` and `security` become ambiguous with the built-ins of
the same name. Running both also loads every skill twice. Pick one.

The plugin ships a SessionStart hook that tells Claude to load the `workflow`
skill before non-trivial code work. You do not need a line in `CLAUDE.md` for
that. If you added one, you can remove it.

### Codex

```sh
codex plugin marketplace add kreek/consult
codex plugin add consult@consult
```

You can also install from `/plugins` inside Codex: find **Consult**, press
Enter to open its details, and select `Install plugin`.

Codex then asks you to review and trust Consult's SessionStart hook. The hook
prints one line telling Codex to load the `workflow` skill before non-trivial
code work. Until you trust it, Codex picks skills from their descriptions alone.

To update, refresh the marketplace and add the plugin again:

```sh
codex plugin marketplace upgrade consult
codex plugin add consult@consult
```

### Cursor

Install from the [Cursor Marketplace](https://cursor.com/marketplace) (search for
**Consult** or submit this repo at
[cursor.com/marketplace/publish](https://cursor.com/marketplace/publish) if it is
not listed yet). Open the marketplace panel in Cursor, install **consult**, then
confirm skills under **Settings → Rules → Agent Decides**. Invoke a skill with
`/skill-name` in Agent chat (for example `/workflow`, `/proof`).

To test from a local checkout before marketplace listing:

```sh
mkdir -p ~/.cursor/plugins/local
cp -R /path/to/consult/plugin ~/.cursor/plugins/local/consult
```

Reload the window (**Developer: Reload Window**). Prefer `cp -R` over symlinks;
some Cursor builds do not load symlinked local plugins reliably.

If you also run `./setup.sh`, Cursor can load the same skills twice (plugin plus
`~/.agents/skills/`). Use either the Cursor plugin or manual install for Cursor,
not both.

Developing inside this repository with a local plugin copy also duplicates skills
(project `agents/.agents/skills/` plus the plugin). See
[`CONTRIBUTING.md`](CONTRIBUTING.md#local-plugin-development).

### Pi

Pi has no Consult package. Use the
[manual install](#manual-multi-agent-or-unsupported-plugins), which links the
skills where Pi reads them.

### Google Antigravity

Antigravity's CLI (`agy`) manages plugins with `agy plugin install`. Consult ships a
ready-to-install plugin at `plugin/` (a `plugin.json` marker plus a `skills/`
directory). Install it from a local checkout:

```sh
agy plugin install /path/to/consult/plugin
```

`agy` copies the plugin into `~/.gemini/antigravity-cli/plugins/consult` and
registers its skills; verify with `agy plugin list`. Because it copies rather
than links, re-run the command (or `./setup.sh`) after pulling new skills.
`./setup.sh` runs this automatically when `agy` is on your PATH.

### Manual (multi-agent or unsupported plugins)

Prerequisites: Git and GNU Stow. Install Stow with one of:

```sh
brew install stow   # macOS
apt install stow    # Debian/Ubuntu
dnf install stow    # Fedora/RHEL
```

```sh
git clone https://github.com/kreek/consult.git
cd consult
./setup.sh
```

`setup.sh` prints the actions it will take and confirms before changing
anything. It links `~/.agents/skills/`, installs the Antigravity plugin via
`agy plugin install`, and links tool-specific skill locations when those tools
are present. End-user installs do not need Python or uv.

### Do I need to add a routing line?

Only the Claude Code and Codex plugins ship the SessionStart hook that tells
the agent to load the `workflow` skill. Antigravity and manual installs have
no hook. Cursor finds the hook file, but we have not confirmed that it
uses the output. On those hosts the agent picks skills from their descriptions
alone. To route non-trivial code work through `workflow`, add this line to the
host's instruction file, for example `AGENTS.md`:

```text
Before a non-trivial feature, fix, refactor, debugging task, test, or config change, load the Consult workflow skill and follow the narrower Consult skills it selects. Skip it for trivial edits and questions that involve no code change.
```

## Skills

Consult includes 24 skills. Open a skill for when it applies and the rules it
sets.

- Routing and proof:
  - [`workflow`](agents/.agents/skills/workflow/SKILL.md): Loads first for non-trivial code changes to choose skills, sign-off gates, and checks.
  - [`proof`](agents/.agents/skills/proof/SKILL.md): Tests, claims, invariants, behavior specs, edge cases, and evidence.
  - [`contract-first`](agents/.agents/skills/contract-first/SKILL.md): Approve caller-facing interfaces or shared structure before implementation.
- Design:
  - [`specify`](agents/.agents/skills/specify/SKILL.md): Design-partner mode for discovery, tradeoffs, decisions, and design artifacts.
  - [`domain-modeling`](agents/.agents/skills/domain-modeling/SKILL.md): Data shapes, invariants, state transitions, parsing, and effects.
  - [`architecture`](agents/.agents/skills/architecture/SKILL.md): Architecture decisions, module boundaries, coupling, layering, and system shape.
- Correctness and change:
  - [`code-review`](agents/.agents/skills/code-review/SKILL.md): Review diffs and PRs for bugs, regressions, edge cases, and merge readiness.
  - [`debugging`](agents/.agents/skills/debugging/SKILL.md): Reproduce symptoms, isolate causes, inspect evidence, and fix bugs.
  - [`error-handling`](agents/.agents/skills/error-handling/SKILL.md): Error types, propagation, retries, user messages, and recovery.
  - [`refactoring`](agents/.agents/skills/refactoring/SKILL.md): Behavior-preserving change, tests, and safe rewrites.
  - [`official-source-check`](agents/.agents/skills/official-source-check/SKILL.md): Version-sensitive framework, library, SDK, or platform behavior, checked against official sources.
- Safety:
  - [`security`](agents/.agents/skills/security/SKILL.md): Auth, secrets, crypto, input validation, dependency risk, and trust boundaries.
  - [`database`](agents/.agents/skills/database/SKILL.md): Schemas, migrations, indexes, transactions, query plans, and locking.
  - [`release`](agents/.agents/skills/release/SKILL.md): Release prep and release-artifact sync, on request or approval.
- Public surfaces:
  - [`api`](agents/.agents/skills/api/SKILL.md): REST API contracts: endpoints, fields, evolution, status codes, errors, pagination, idempotency.
  - [`documentation`](agents/.agents/skills/documentation/SKILL.md): READMEs, runbooks, API docs, module docs, and comments for existing code.
  - [`ui-design`](agents/.agents/skills/ui-design/SKILL.md): Frontend UI, layouts, components, responsive behavior, accessibility, WCAG, keyboard, and focus.
- Production quality:
  - [`async-systems`](agents/.agents/skills/async-systems/SKILL.md): Message contracts and schemas, queues, streams, concurrency, ordering, and backpressure.
  - [`observability`](agents/.agents/skills/observability/SKILL.md): Production logs, metrics, traces, health checks, alerts, SLOs, and performance measurement.
  - [`performance`](agents/.agents/skills/performance/SKILL.md): Profiling, latency, throughput, allocation, caching, and hot paths.
- Repo workflow:
  - [`commit`](agents/.agents/skills/commit/SKILL.md): Staging reviewed work, commit splits, and messages.
  - [`scaffolding`](agents/.agents/skills/scaffolding/SKILL.md): New projects, package setup, quality tooling, CI, and repo structure.
  - [`git-workflow`](agents/.agents/skills/git-workflow/SKILL.md): Branches, history edits, conflicts, rebases, recovery, and force-push.
  - [`issue-tracking`](agents/.agents/skills/issue-tracking/SKILL.md): Initiatives, epics, and issues in GitHub, Jira, or another tracker: drafting, sizing, linking, and status.

Greenfield stack templates live under
[`scaffolding/references/stacks/`](agents/.agents/skills/scaffolding/references/stacks/).
Shared language defaults are in
[`language-defaults.md`](agents/.agents/skills/scaffolding/references/language-defaults.md).

## Writing documents with Terse

Consult's `documentation` skill covers docs for existing code. For specs, ADRs,
design docs, PR descriptions, and posts, use
[Terse](https://github.com/kreek/terse), a companion plugin from the same
author. Terse pairs an offline style checker with skills to brainstorm,
outline, draft, and edit, and it keeps the writer's voice. It needs Node.js 18
or newer.

In Claude Code:

```text
/plugin marketplace add kreek/terse
/plugin install terse@terse
```

In Codex:

```sh
codex plugin marketplace add kreek/terse
codex plugin add terse@terse
```

## How routing works

The `workflow` skill loads first for non-trivial code work. It picks the
narrower skills that change what the agent does next or how it checks the
result.

The agent asks for sign-off before it builds any of these:

- the design direction
- a caller-facing interface
- a core data shape that future work binds to
- a migration or destructive data change
- a release artifact
- a history-changing or destructive git operation

Local helpers, private file moves, and narrow bug fixes that restore intended
behavior never need sign-off. Some runs have no human to answer, such as
headless or scheduled runs. There the agent builds the most conservative
version, marks it provisional, and flags the decision.

When work needs approval before building, the agent saves the approved plan as
Markdown. A fresh session, or a cheaper model, can then build from the plan
without the planning conversation.

See [`workflow`](agents/.agents/skills/workflow/SKILL.md) for the full
routing table and [`contract-first`](agents/.agents/skills/contract-first/SKILL.md)
for sign-off on interfaces and shared structure.

## Evaluation

[`eval/README.md`](eval/README.md) benchmarks Claude Code and Codex with and
without Consult on shared engineering tasks, using Harbor for sandboxed trials
and RewardKit for scoring. It combines deterministic hidden tests with
LLM-judged engineering maturity, proof quality, simplicity, and risk handling.
It reports the lift from installing Consult.

## Contributing

See [`CONTRIBUTING.md`](CONTRIBUTING.md) for project conventions, the skill
authoring template, branching rules, checks, and maintenance steps. Skill
authoring rules and pack-versioning policy live in
[`AGENTS.md`](AGENTS.md#skill-anatomy-enforced-by-the-validator).

## License

MIT: see [`LICENSE`](LICENSE).

## Uninstall

Manual install:

```sh
stow --target="$HOME" -D agents
```

Manual cleanup may still be needed for tool-specific symlinks.

If you installed the Claude Code plugin, run these from inside Claude Code:

```text
/plugin uninstall consult@consult
/plugin marketplace remove consult
```

For Codex:

```sh
codex plugin remove consult@consult
codex plugin marketplace remove consult
```

For Cursor,
disable or uninstall **consult** from the marketplace panel (or remove
`~/.cursor/plugins/local/consult` and any `~/.cursor/plugins/cache/consult` copy). For
Antigravity, run `agy plugin uninstall consult`.
