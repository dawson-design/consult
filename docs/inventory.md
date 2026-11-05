# Consult v1 → v2 decision inventory

This lists every v1 rule (core plus 17 skills) and what v2 does with it. Approved on
2026-11-03. The open calls are resolved at the end of this file, and D1–D18 were
accepted as proposed. The eval decides whether each default stays.

v2 rule ids:
- `core.N`: the core rules.
- `default.N`: the house defaults, renumbered in `core.md` as 1–15 (see the mapping
  below).
- `human.N`: working with the human.
- `<skill>.N`: skill rules.

## Columns

- **id:** v1 skill and rule number, current numbering. Eval ids in
  `../consult/eval/verifier/rules.json` use the same numbers.
- **Kind:**
  - `O` opinion: picks one of several good options.
  - `F` floor: a concrete threshold or trap that models often miss.
  - `B` best practice: a strong engineer does it unprompted.
  - `P` process: a gate, a routing step, or ceremony.
- **Lift:** the measured per-rule lift from the 2026-11-02 rules suite (Opus 5.5,
  xhigh effort, 3 tasks). `chk` means an eval check exists but the rule wasn't
  exercised, and `–` means the rule is untested. Only 12 of 124 rules have checks.
- **Proposal:**
  - `CORE-R`: a core rule.
  - `CORE-D`: a row in the core house-defaults table.
  - `CORE-H`: the "working with the human" section of core.
  - `SKILL:x`: a rule in skill x.
  - `REF:x`: a reference file of skill x.
  - `CUT`: dropped.

## Measured lift in one line

Five rules gained a full 1.0 or 0.5, and all five pick a side or set a floor:
- `scaffolding.5`, `scaffolding.6`, and `scaffolding.7` (standard commands, a real typecheck, a pinned toolchain).
- `domain-modeling.7` (an approval checkpoint for the core model, +1.0).
- `domain-modeling.8` (the money and dates floors, +0.5).

`api.1` (spec first) and `documentation.1` gained +0.25. All the other measured rules were 0.0.

---

## 1. Core rules (always on)

| id | Rule (short) | Kind | Lift | Proposal |
|---|---|---|---|---|
| core.iron | Complexity is the enemy: keep software simple enough to understand, change, and prove | O | – | CORE-R (sentence case) |
| core.1 | Keep calculations, I/O, and state separate. Pure calculations, effects at the edges | O | – | CORE-R |
| core.2 | Build only what was asked. No unrequested routes, flags, config, or env vars; propose them instead | O | – | CORE-R (as a constraint) |
| core.3 | Look for a maintained library first. Mature, current versions. Ask before adding a dependency | O | – | CORE-R |
| core.4 | Readable in one pass: about 25–30 line functions, under 3 nesting levels, named compound conditions, composition over inheritance | O/F | – | CORE-R. The inheritance clause moves to CORE-D Paradigm |
| core.5 | Report what needs attention first, then what changed, why, proof, and what's unproven | P | – | CORE-H (adds "how it works") |
| core.6 | Ask whether backward compatibility is needed. No shim until answered | O | – | CORE-R |
| core.7 | Treat input that crosses a trust boundary as untrusted. Parse or validate it | B/F | – | CORE-R (one line) |
| core.8 | Run lint, typecheck, and the format check before commit. Propose missing tools | F | – | CORE-R |

## 2. Proposed house defaults (CORE-D)

**Set your preference on each row.** Each row reads *decision → our choice → unless*,
and following the project's existing choice always wins.

| # | Decision | Our choice | Unless | From |
|---|---|---|---|---|
| D1 | Paradigm | Functional core, imperative shell. Immutable records, sum types, maps, and functions. A class that only wraps pure functions is a module. No classes that combine behavior with mutable state, and no inheritance | A framework or the codebase requires classes | core.4, dm.2, dm.3 |
| D2 | Structure | DDD vocabulary: organize by domain feature or bounded context, keeping behavior, data, and tests together. No horizontal layers except at a real boundary (process, deploy, trust, persistence, transport) | The repo is already layered | arch.1, arch.2 |
| D3 | DDD tactical patterns | Use aggregates, repositories, and domain services only when they protect a real invariant or a term with two meanings | — | arch.5 |
| D4 | Names | Use the project glossary, else the words of the spec or issue. One term per concept per context. Use domain verbs (`settleInvoice`), not `process`/`handle`/`Manager` | A framework boundary requires a generic name | dm.6, dm.9 |
| D5 | Expected failures | Return Result-style values. Exceptions are for bugs. No bare strings or generic errors | The project uses typed exceptions | eh.1 |
| D6 | Catching | Catch only to recover, translate, retry, or terminate, and keep the cause. Translate errors at each boundary. Fail closed on auth, validation, and crypto | — | eh.2, eh.3 |
| D7 | State modelling | Explicit variants, not flag or nullable combinations | A single independent boolean | dm.5 |
| D8 | Input parsing | Parse once at the boundary into trusted types with Zod (TS) or Pydantic (Py). Raw maps don't cross the boundary | An existing schema library | dm.4, arch.4 |
| D9 | Security primitives | Don't hand-roll auth, crypto, tokens, sanitizers, CSRF, or URL parsers. Use the framework or a maintained library | A documented need, a threat model, and negative tests | dm.4 |
| D10 | Contracts | Write the contract (OpenAPI, types, schema) before the code that implements it | A fix that restores existing behavior | api.1, contract-first |
| D11 | Live updates | Polling, SSE, or WebSockets. Kafka or streams only once you can name the need (replay, retention, fan-out) | — | arch.6 |
| D12 | Remote calls | Declare timeout, retry (idempotent only, one layer, capped, jittered), and failure mode together | — | eh.4 |
| D13 | Secrets in errors and logs | Redact with a field allowlist, not a deny-list. No secrets, SQL, paths, or stack traces in user-facing errors; use a correlation id | — | eh.5 |
| D14 | Toolchain | uv / pnpm or bun / cargo / go mod. One lockfile, a pinned language version, and standard `test` `lint` `format` `typecheck` commands | The project uses other tools | scaf.5–7 (+1.0) |
| D15 | Refactors | Keep structural and behavioral changes in separate commits. Use parallel change (expand, migrate, contract) for public interfaces. No big-bang rewrites | You approve a rewrite of a small, disposable scope | ref.1, ref.3, ref.5 |
| D16 | Git | `feature/`, `fix/`, or `refactor/` topic branch off the default. Stage files by name. One revertible behavior per commit. Subject completes "this commit will…" in under 72 chars. Never skip hooks | — | commit.2–4, commit.6, gw.1 |
| D17 | Uniqueness | Enforce every uniqueness invariant with a database constraint, not an app-level check | — | db.4 |
| D18 | Docs | Encode rules in names, types, and tests first. Comments explain only the non-obvious why | — | doc.3 |

## 3. Working with the human (CORE-H) — replaces workflow and contract-first

| id | Rule (short) | Kind | Lift | Proposal |
|---|---|---|---|---|
| wf.1 | Ask more as risk and blast radius grow. Offer options with a recommendation | P | 0.0 | CORE-H, rewritten as the two checkpoints |
| wf.2 | Approval list: design, contracts, core data and invariants, migrations or data deletion, release, git history | P | – | CORE-H (adds new dependency and publishing) |
| dm.7 | Approve the core model or invariant before building on it | P | **+1.0** | CORE-H checkpoint 2 |
| cf.1–6 | What counts as a contract. Approval covers only what was shown. Silence isn't approval. Stop if the contract must change | P | – | CORE-H, merged to about 3 lines |
| wf.3 | Plan with the strongest model and save the plan for a cheaper one | P | – | CUT (host plan mode saves plans) |
| wf.4 | Build data → contracts → transformations, with sign-off per stage | P | – | Replaced by checkpoint 2 (data and contracts shown with proof, then logic) |
| wf.steps 1–5 | Routing table, load every match, mandatory review, re-review | P | – | CUT. Skills trigger by description. Review is user-invoked, in a fresh session before commit |
| wf.refs | `plans.md`, `long-runs.md`, `stages.md`, `core.md` copy | P | – | CUT (`core.md` copy is generated for Codex later) |
| new | Final report includes *how it works*: where data enters, the key decision, which file to read first | — | – | CORE-H (from the skill-formation research) |
| new | Record checkpoint decisions in the project's ADRs or decision log when it has one | — | – | CORE-H |

## 4. Skills kept (model-invoked)

### proof (unchanged rules; wording only)

| id | Rule (short) | Kind | Lift | Proposal |
|---|---|---|---|---|
| proof.iron | Every acceptance criterion needs a check that fails when it's not met | O | – | SKILL:proof |
| proof.1 | Every reported claim needs a check, else it's marked unproven. Version-specific API claims checked against the installed version and docs | F | – | SKILL:proof |
| proof.2 | A bug fix starts with a failing reproduction and a one-sentence root cause. A refactor keeps the same checks green | O | chk | SKILL:proof |
| proof.3 | Tests assert business rules with expected values from the spec. Choose the level and say why. Custom guards get a negative test | O/F | – | SKILL:proof |
| proof.4 | Use real code, mock only network and filesystem. Fix clock, random values, and ids | O | – | SKILL:proof |
| proof.5 | Fix flaky tests at the cause, no sleeps or retries | B | – | SKILL:proof |
| proof.6 | See each criterion's check fail once (break the change by hand if the test was written after) | O | – | SKILL:proof (kept, per your call) |
| proof.7 | Check config and docs by running them, not asserting their text | F | – | SKILL:proof |
| proof.8 | Run existing tests first. Never weaken a test to make a change pass | F | – | SKILL:proof |
| proof.9 | Re-read the request, rerun the whole suite once, list each criterion with its status | P | – | SKILL:proof (kept, per your call) |
| proof.refs | `black-box.md` (1,663 words), `test-theater.md` | F | – | REF:proof, both kept. Trim black-box to opinions and traps (target about 900 words)? **Your call** |
| proof.handoffs | Links to domain-modeling, api, refactoring, error-handling | P | – | CUT |

### api

| id | Rule (short) | Kind | Lift | Proposal |
|---|---|---|---|---|
| api.iron | Spec first. Preserve shipped consumers. Pick status by failure | O | – | SKILL:api |
| api.1 | OpenAPI sketch before the handler. List every response | O | +0.25 | SKILL:api (core D10 is the general form) |
| api.2 | Keep independent consumers working: successor or deprecation window, RFC 9745/8594 headers, one versioning scheme | O/F | 0.0 | SKILL:api |
| api.3 | Status table by where the failure starts. Never pass upstream status through | O/F | 0.0 | SKILL:api |
| api.4 | Keep the existing representation. New REST APIs default to JSON:API, errors use RFC 9457 when there's no native format | O | – | SKILL:api |
| api.5 | Middleware only for transport-wide concerns. Authz and invariants live at the route or domain | O | – | SKILL:api |
| api.6 | Idempotency, pagination, and webhook floors | F | – | SKILL:api plus REF (all 4 refs kept) |

### database

| id | Rule (short) | Kind | Lift | Proposal |
|---|---|---|---|---|
| db.iron | Protect production data: prove rollout, locking, and recovery first | O | – | SKILL:database |
| db.1 | Destructive or hard-to-reverse changes are the user's call | P | – | CORE-H (approval list). Skill keeps a one-line pointer |
| db.2 | Expand → migrate → verify → switch → contract | O | – | SKILL:database |
| db.3 | Review raw SQL and locks. Use the online mechanism. SQLite isn't proof of Postgres behavior | F | – | SKILL:database |
| db.4 | Uniqueness enforced by a database constraint | F | – | CORE-D D17 and SKILL:database |
| db.5 | Document rollback and backup/PITR coverage | F | – | SKILL:database |
| db.6 | Index each foreign key or known predicate. Batched, resumable backfills. Transactional outbox, no dual writes | O/F | – | SKILL:database |
| db.refs | `online-ddl.md` | F | – | REF:database |

### ui-design

| id | Rule (short) | Kind | Lift | Proposal |
|---|---|---|---|---|
| ui.iron | Start from the user task. Remove what it doesn't need. WCAG 2.2 AA is the floor | O | – | SKILL:ui-design |
| ui.1 | One dominant primary action per screen. Cards only for peer items | O | – | SKILL:ui-design |
| ui.2 | Task and flow before framework. Design system: the product's, else HIG / Material 3 / Carbon | O | – | SKILL:ui-design |
| ui.3 | A small token system, no stray one-off values | O | – | SKILL:ui-design |
| ui.4 | Loading, empty, error, disabled, and success states designed with the layout | B | – | SKILL:ui-design (one line) |
| ui.5 | Native HTML before ARIA. Visible text is the name, `aria-label` only on icon-only controls | F | – | SKILL:ui-design |
| ui.6 | Visible focus: 2px at 3:1, Forced Colors fallback, no positive tabindex, focus restored | F | – | SKILL:ui-design |
| ui.7 | Explicit labels, errors tied to fields, no placeholder-only text, single-pointer alternative to drag | F | – | SKILL:ui-design |
| ui.8 | Manual keyboard and screen-reader testing. Record any gaps | F | – | SKILL:ui-design |
| ui.refs | `accessibility.md`, `canon.md`, `platforms.md`, `editorial.md` | F/O | – | Keep accessibility and canon. CUT platforms and editorial? **Your call** |

### scaffolding

| id | Rule (short) | Kind | Lift | Proposal |
|---|---|---|---|---|
| scaf.iron | No feature code before the toolchain proves it can fail and pass | O | – | SKILL:scaffolding |
| scaf.1 | Scaffold Decision Gate menu before creating files | P | 0.0 | SKILL:scaffolding, as the plan checkpoint (no separate menu) |
| scaf.2 | Research dependencies freely. Approve structural ones | P | – | CORE-H (new dependency) |
| scaf.3 | Recommend one option per choice. Fresh web apps use a mature framework | O | – | SKILL:scaffolding |
| scaf.4 | Requested file names are literal | F | – | SKILL:scaffolding |
| scaf.5 | Standard commands. CI runs them. Pre-push hook runs the fast checks | O | **+1.0** | SKILL:scaffolding and CORE-D D14 |
| scaf.6 | `typecheck` runs a real type checker | F | **+1.0** | SKILL:scaffolding |
| scaf.7 | git, `.gitignore`, one lockfile, pinned version, smoke test, `.env.example`, README | F | **+1.0** | SKILL:scaffolding |
| scaf.8 | Prototypes keep the same command names | O | – | SKILL:scaffolding |
| scaf.refs | `stacks.md`, `language-defaults.md` | O | – | REF:scaffolding (merge into one file) |

### domain-modeling (thin, hosts money and dates)

| id | Rule (short) | Kind | Lift | Proposal |
|---|---|---|---|---|
| dm.iron | Illegal states are unrepresentable in the domain core | O | – | SKILL:domain-modeling |
| dm.1 | Decide data shapes and invariants before transformations | O | – | CORE-H checkpoint 2 |
| dm.2–6, dm.9 | Paradigm, data/calc/action split, parsing, variants, names, glossary | O | – | CORE-D (D1, D4, D7, D8, D9) |
| dm.7 | Core model approval | P | **+1.0** | CORE-H |
| dm.8 | Load `dates.md` or `money.md` when the diff touches dates or money | F | **+0.5** | SKILL:domain-modeling (description triggers on money and dates) |
| dm.refs | `money.md`, `dates.md` | F | – | REF:domain-modeling |

### code-review (user-invoked, in a fresh session before commit)

| id | Rule (short) | Kind | Lift | Proposal |
|---|---|---|---|---|
| cr.iron | Findings first. Block on correctness, safety, data loss, missing proof | O | – | SKILL:code-review |
| cr.1 | Review finds defects. Proof writes the checks | P | – | CUT |
| cr.2 | Findings by severity, with anchor, impact, fix, and evidence. Severity table | O | – | SKILL:code-review |
| cr.3 | Security pass and proof pass. Red CI means unproven. Dependency audit when auth or deps change | F | – | SKILL:code-review |
| cr.4 | Maintainability findings need a concrete risk. Style doesn't block | O | – | SKILL:code-review |
| cr.5 | Agent-mistake list: speculative abstraction, shims, test theater, fabricated APIs, scope creep | F | – | SKILL:code-review |
| cr.6 | Diff too big for one sitting is a finding, with a suggested split | O | – | SKILL:code-review and CORE-H |
| cr.indep | Fresh context. Reviewer gets diff, intent, and constraints, not the author's rationale | O | – | SKILL:code-review. Runs only when the user invokes it |
| cr.refs | 9 language guides (about 3,000 words) | B/F | – | Keep typescript and python cut to traps (about 300 words each). CUT the other 7? **Your call** |

### git (merges commit and git-workflow)

| id | Rule (short) | Kind | Lift | Proposal |
|---|---|---|---|---|
| commit.iron / gw.iron | Commit only the reviewed slice, stage by name. Never rewrite shared history or skip recovery | O | – | SKILL:git |
| commit.1 | Check tree state first. Stop on anything unexpected | B | – | SKILL:git (one line) |
| commit.2–4, commit.6 | Group by behavior, stage by name, subject format, never skip hooks | O | – | CORE-D D16 |
| commit.5 | Attribution trailers are host config | O | – | CUT (your CLAUDE.md already covers it) |
| gw.1 | Branch without ceremony. Don't ask which branch | O | – | CORE-D D16 |
| gw.2 | Host permissions own GitHub access. No second ask | O | – | SKILL:git |
| gw.3 | Humans approve PR and issue text and each published write | P | – | SKILL:git and CORE-H (publishing) |
| gw.4 | Inspect state, name a recovery point, `--force-with-lease --force-if-includes` | F | – | SKILL:git |
| gw.5 | Resolve conflicts preserving both intents. Verify with range-diff. Regenerate generated files | F | – | SKILL:git |
| gw.6 | Test hook policy, not hook wrappers | O | – | CUT (rare) |
| gw.7 | Branch in the main checkout. Worktrees only for parallel work | O | – | SKILL:git |

## 5. Skills made user-only (`disable-model-invocation: true`)

These cost no context until you invoke them. Their rules port as-is after a light trim.

| skill | rules | Proposal |
|---|---|---|
| release | 1–8 (late gate, humans mutate shared environments, per-unit bump, artifacts together, rollback, flags) | Port. CUT the Workflow section and handoffs |
| issue-tracking | 1–10 (three levels, sprint sizing, split by behavior, under 200 words, team owns fields) | Port. Refs: keep templates and github, CUT jira and other-trackers? **Your call** |
| documentation | 1–6 (only when asked, link the source of truth, README shape, voice) | Port. D18 moves rule 3 into core |

## 6. Skills folded into core and deleted

| skill | where its rules go |
|---|---|
| workflow | CORE-H (section 3). The routing table and staged gates are cut |
| architecture | arch.1, 2, 5 → D2/D3. arch.4 → D8. arch.6 → D11. arch.3 (boundary states its contract) → CUT, covered by D10 |
| contract-first | CORE-H |
| error-handling | eh.1–5 → D5, D6, D12, D13. eh.6 (failure-path test) → SKILL:proof as one clause? **Your call** |
| refactoring | ref.1, 3, 5 → D15. ref.2 (name the coupling, characterization tests) → SKILL:proof (proof.2 already covers green before and after). ref.4 (simpler means less hidden state) → CUT |

## Resolved calls

1. `proof/references/black-box.md` trimmed: the Canon citations were cut, and every rule
   was kept (1,663 → 943 words).
2. ui-design keeps only `accessibility.md` and `canon.md`.
3. code-review keeps no language guides.
4. issue-tracking keeps only `templates.md` and `github.md`.
5. eh.6 (failure-path test) added to `proof` Rule 3.
6. D1–D18 accepted as proposed.

## Inventory id → core.md id

| Inventory | core.md | Inventory | core.md |
|---|---|---|---|
| D1 | default.1 Paradigm | D10 | default.7 Contracts |
| D2, D3 | default.2 Structure | D11 | default.8 Live updates |
| D4 | default.3 Names | D12 | default.9 Remote calls |
| D5, D6 | default.4 Errors | D13 | default.10 Secrets |
| D7, D8 | default.5 Data | D14 | default.11 Tooling |
| D9 | default.6 Security primitives | D15 | default.12 Refactors |
| D16 | default.13 Git | D17 | default.14 Uniqueness |
| D18 | default.15 Comments | | |

v1 core rules 1–8 became `core.1`–`core.7` (v1 core.5, the report, is now `human.7`).
The eval check ids were renamed: `domain-modeling.7` → `human.1`,
`domain-modeling.8` → `domain-modeling.2`, and `workflow.1` → `human.4`.
