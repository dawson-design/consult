---
name: code-review
description: Reviewing a diff, branch, or PR for bugs, regressions, missing tests, and merge readiness.
---

# Code Review

## Iron Law

`FINDINGS FIRST. BLOCK ON CORRECTNESS, SAFETY, DATA LOSS, AND MISSING PROOF.`

## When to Use

- Independent review of your diff at `workflow` step 5, after
  `proof` and before saying done. Default for any non-trivial
  agent-generated change.
- Diff review: local, branch, or a GitHub PR through the host's GitHub tools.
- Review-comment follow-up on the user's own PRs.

## When NOT to Use

- Commit grouping or history repair only; use `git-workflow`.
- A narrow domain-only review where `database`, `api`, or
  `ui-design` is sufficient.

## Rules

1. Review finds defects; `proof` writes the checks. Find behavioral bugs,
   regressions, unsafe edge cases, and merge blockers.
2. Reports to the requester put findings first by severity. Each names a
   file/line or thread anchor, issue, impact, fix direction, and evidence or
   missing proof. Summaries follow. Ask only when uncertainty blocks a finding.

   | Severity | When to use |
   |---|---|
   | Critical | Exploitable security, data loss, broken auth, destructive migration, outage risk |
   | High | Incorrect behavior, broken contract, missing authorization, race, serious regression |
   | Medium | Maintainability, error handling, observability, compatibility, or test gaps likely to cause defects |
   | Low | Non-blocking clarity, skip unless asked |

3. Every review includes a security pass and a proof pass: each acceptance
   criterion has a check that fails when it is not met. Anything reported as
   true that the review cannot verify is unproven. Red or absent CI makes the
   review unproven; review the code anyway. Missing intent on a non-trivial PR
   is a finding. Repository constraints beat generic advice: check the
   declared runtime, framework, dependency, CI, and support policy before
   applying a language reference. A change that touches auth, secrets, or
   dependencies also gets the ecosystem's dependency audit and a secrets
   scan.
4. Maintainability findings need a concrete risk: hidden state, coupled
   effects, stale flags, duplicated rules with divergent meaning, dead
   compatibility, unreachable paths. Style is not blocking unless it hides
   ambiguity or unsafe control flow.
5. Check agent-written code for agent mistakes: speculative abstraction,
   unnecessary shims, dead defensive code, test theater, fabricated APIs,
   scope creep, refactors that change behavior, and code too large or vague
   for a human to hold in their head. Hand-rolled versions of solved problems (HTTP
   clients, ORMs, parsers, retry loops, validators, crypto) are findings. A
   shim that stays names its owner, its caller, the condition for removing
   it, and its proof.
6. If a human can't review the diff in one sitting, say which part you
   reviewed, and report the size as a finding with a suggested split. Ask for
   reformatting and unrelated edits to be split out before deep review. Skim
   generated, vendored, and lockfile changes for obvious risk. The exception
   is generated code people will keep and read: review it in full and count
   it toward the diff size.

### Independent Review

Code review runs in a fresh context: a subagent, review agent, fresh session,
or host review command. Claude Code, Codex, and Cursor all have a
mechanism. Same-context review is not code review, only a labelled fallback
when the host truly lacks one, and its clean result is weaker evidence. The
reviewer gets exactly these inputs:

- The diff.
- The stated intent and acceptance criteria.
- The repo's declared constraints: runtime, framework, support policy, test
  command.

Withhold the implementation rationale. Why a line is there is what biases a
reviewer into accepting it; one who works the intent out from the diff finds
what the author's second pass cannot. Answer the reviewer's questions, but do
not pre-empt them with justification.

## Workflow

1. Find the target, then check the intent, impact, CI status, changed files
   and contracts, and the scope you can honestly cover.
2. Load only what the diff needs: the language guide for each language present
   and the domain skill for each touched risk. Load `release` only for
   concrete release artifacts or explicit release-readiness review.
3. Check each risk: security, behavior, proof, dead code, reuse, and the
   Rule 5 list.
4. Write findings first. If none, name residual risk and unreviewed scope.

## Handoffs

- `database`: migrations, locking, transactions, schema, indexes.
- `release`: version, changelog, package, publish, or rollout readiness.
- `proof`: missing behavior coverage, test quality, mocks, flakes.
- `git-workflow`: branch mechanics and packaging accepted fixes.

## References

- Language reviewer guides, load one per language in the diff:
  `references/fsharp.md`, `references/csharp.md`, `references/python.md`,
  `references/typescript.md`, `references/ruby.md`, `references/java.md`,
  `references/kotlin.md`, `references/bash.md`, `references/sql.md`.
