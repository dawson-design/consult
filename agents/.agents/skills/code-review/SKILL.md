---
name: code-review
description: "Fresh-context review of a diff, branch, or PR for bugs, regressions, security gaps, missing proof, and agent mistakes, reported as findings by severity. Invoke with /consult:code-review in a new session before committing."
disable-model-invocation: true
---

# Code review

## Iron law

Findings first. Block on correctness, safety, data loss, and missing proof.

## Rules

1. Review in a fresh context: a subagent, a fresh session, or the host's
   review command. Give the reviewer only the diff, the stated intent and
   acceptance criteria, and the repo's declared constraints (runtime,
   framework, support policy, test command). Withhold the implementation
   rationale, because it biases the reviewer toward accepting the code.
   Review once; after fixes, report what remains instead of reviewing again.
2. Report findings first, by severity. Each names a file and line, the
   issue, its impact, a fix direction, and the evidence or missing proof.
   Ask only when uncertainty blocks a finding.

   | Severity | When |
   |---|---|
   | Critical | Exploitable security, data loss, broken auth, destructive migration, outage risk |
   | High | Incorrect behavior, broken contract, missing authorization, race, serious regression |
   | Medium | Error handling, compatibility, or test gaps likely to cause defects |
   | Low | Non-blocking clarity; skip unless asked |

3. Every review includes a security pass and a proof pass: each acceptance
   criterion has a check that fails when it is not met. Red or absent CI
   makes the review unproven; review the code anyway. A change to auth,
   secrets, or dependencies also gets the ecosystem's dependency audit and a
   secrets scan.
4. A maintainability finding names a concrete risk: hidden state, coupled
   effects, stale flags, duplicated rules with diverging meaning, dead
   compatibility code, unreachable paths. Style doesn't block unless it
   hides ambiguity or unsafe control flow.
5. Check for agent mistakes: speculative abstraction, unneeded shims, dead
   defensive code, test theater, fabricated APIs, scope creep, refactors
   that change behavior, hand-rolled versions of solved problems, and code
   too large or vague for a person to hold in their head.
6. If one person can't review the diff in one sitting, say which part you
   reviewed and report the size as a finding with a suggested split.
