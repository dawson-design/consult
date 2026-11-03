---
name: workflow
description: Load before reading code for any feature, bug fix, refactor, test, or config change. Then load the skills it names.
---

# Workflow

## When to Use

- Use first for features, fixes, refactors, debugging, and tests.
- Also use for UI, docs, config, CI, dependencies, and investigations that
  guide later code changes.

## When NOT to Use

- The user names a narrower skill that covers the whole task.
- The change is trivial, with no behavior, contract, data, or security risk.
- Platform operations with no code, contract, or proof question.

## Rules

If the block that starts "Consult is installed." is not in your context,
read `references/core.md` (the Consult core) before your first edit. Its
rules apply with these.

1. **Ask more of the user when changes affect more code or are harder to
   undo.** If both risks are low, do the work and prove it without sign-off.
   For higher risk, give progress updates, explain options, and get approval
   before acting.
2. **Get the user's approval before you build any of these:**
   - the design direction
   - a contract that callers depend on
   - a core data shape, invariant, or glossary term later work depends on
   - a migration, or a change that deletes or rewrites data
   - a release artifact
   - a change to git history, or any destructive git operation
3. **Plan with the strongest model, and save the plan so a cheaper one can
   build it.** When Rule 1 calls for approval before building, save the
   approved plan as `references/plans.md` describes. When building from a
   plan, follow it, and stop to ask when it is wrong or incomplete. When you
   delegate, give read-only search and tool-verified mechanical fixes the
   host's cheapest capable model and the fresh-context review its
   strongest; never set effort below the host default for work that needs
   reasoning.
4. **Build in stages, and prove each before building the next.** Order:
   data (records, relationships, invariants, schema); contracts
   (caller-facing boundaries and the shell that parses input, reads and
   writes data, and renders output); transformations (pure logic between
   parsed input and output). Skip stages the change does not touch. Before
   building a stage that holds a Rule 2 item no approved plan shows, show
   the earlier stages with their evidence and get sign-off on them. A Rule 2
   item an earlier stage changed from what the plan showed needs sign-off
   again. An approved plan covers the stages it shows, so build them without
   stopping again.

## Workflow

1. State what should change, who it affects, how you will check it, and what
   else it may affect. If the desired result is unclear, propose acceptance
   criteria and ask one question at a time.
2. **Before your first edit, load every skill whose row in this routing table
   matches the task, and no others.** Its checks apply even when the fix
   looks obvious. Match the request first, then the code you read. Load
   `code-review` at step 5. Prefer Consult skills to same-named host
   skills.

   | Skill | Load when |
   | --- | --- |
   | `specify` | A significant or hard-to-change choice is unsettled. |
   | `contract-first` | A caller-facing interface or shared structure needs approval. |
   | `domain-modeling` | Data shape, states, invariants, transitions, or effects. |
   | `architecture` | Module boundaries, ownership, layering, cross-component structure, live-update transport. |
   | `refactoring` | Structure must change while preserving behavior. |
   | `api` | HTTP/API shape, status codes, pagination, idempotency, webhooks. |
   | `database` | Persisted data, migrations, transactions, deletion, queries. |
   | `error-handling` | Error types, propagation, recovery, retries, user-facing failures, auth, permissions, secrets. |
   | `ui-design` | Any user-facing UI surface, including basic styling, keyboard, focus, ARIA, contrast. |
   | `documentation` | Existing-code docs are the deliverable or a validator-required obligation. |
   | `scaffolding` | New project setup or baseline tooling. |
   | `proof` | Any non-trivial change. |
   | `code-review` | A review is requested, or the change is non-trivial. |
   | `commit` | The user asks to commit: staging, splitting commits, writing messages. |
   | `git-workflow` | The user asks for branches, worktrees, conflicts, rebases, recovery, force-push, or GitHub access, or approved work needs them. |
   | `issue-tracking` | Drafting, splitting, or tracking initiatives, epics, or issues, or a task citing one. |
   | `release` | Release prep is requested or a validator requires artifact sync. |

3. Apply Rule 1, then build each Rule 4 stage in order and prove its
   behavior with `proof` before building the next.
4. Make changes small enough to review. If a change grows too large for one
   focused review, split the rest into reviewable plan steps and continue.
5. After the last stage, run one fresh-context `code-review` with its
   Independent Review inputs plus the proof evidence, and fix its findings.
   Run a second review only when the first reported Critical or High
   findings, and give it only the fix diff and those findings. Report what
   remains open instead of reviewing again. Finish documentation and release
   work afterward.

## References

- `references/plans.md`: load when saving an approved plan or building from
  one.
- `references/long-runs.md`: load when work spans many steps or independent
  units, or before delegating build work to a subagent.
- `references/stages.md`: load when a change spans more than one Rule 4
  stage, behavior slices, a removal or rename, or a phased schema rollout.
