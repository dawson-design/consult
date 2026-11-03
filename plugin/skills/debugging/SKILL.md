---
name: debugging
description: A bug report, wrong output, crash, failing or flaky test, or regression. Load before editing to find the cause.
---

# Debugging

## Iron Law

`NO FIX WITHOUT ROOT-CAUSE EVIDENCE.`

## When to Use

- Defects, flakes, timing-sensitive bugs, regressions, production incidents,
  unclear failures, or stuck debugging sessions.

## When NOT to Use

- Planned refactors with no failing behavior; use `refactoring`.
- Slowness as the symptom; use `performance`.
- Bisect and reflog mechanics; pair with `git-workflow`.

## Rules

1. Reproduce before fixing, or record why reproduction is not yet possible.
   Capture the exact symptom: command, input, output, stack trace, timing,
   environment.
2. One hypothesis at a time. Predict what else must be true, run the smallest
   experiment that confirms or refutes it, and change one variable per
   experiment. After the third experiment, keep a short debug log.
3. Before editing, state the failure model: likely cause, evidence for it,
   and the observation that would disprove it. A fix you cannot explain is
   not a fix.
4. The root cause is named in one sentence, explains every observed symptom,
   and names the evidence that ruled out the main alternatives.
5. The fix is one atomic change aimed at that cause, with a regression test
   or operational guard that fails before and passes after.
6. A flake is a bug. Identify whether the test, the code, or the environment
   failed; never retry it away.
7. Timing-sensitive bugs are verified with non-invasive observation or
   replay, not by adding sleeps.
8. Incidents produce blameless learning with owned, dated follow-ups. "Human
   error" is never the root cause.
9. A root cause or fix you have not proven is reported as unproven.

## Handoffs

- `proof`: evidence that the fix works, and the regression test's design.
- `git-workflow`: `git bisect`, reflog recovery, conflict-heavy debugging.
- `observability`: evidence that must come from logs, metrics, or traces.
- `error-handling`: a root cause in an error boundary, retry, or timeout.
