---
name: proof
description: "Writing or changing tests, or proving a change meets its acceptance criteria: edge cases, invariants."
---

# Proof

## Iron Law

`EVERY ACCEPTANCE CRITERION NEEDS A CHECK THAT FAILS WHEN THE CRITERION IS NOT MET.`

Acceptance criteria are the results the request asks for, whether they come
from a ticket, a spec, or a one-line prompt. If none are written down, list
them from the request in a sentence or two before choosing checks. A check is
a test, or a command you run and read. Each criterion needs at least one
check where the caller would see the result: the endpoint, CLI, UI, or public
API. Rule 3 says which other tests fit below that. Write checks before or
after the code; Rule 6 says how to see each one fail. "The tests pass" does
not count until you can say which criterion each test proves.

## When to Use

- Before any reply that says or implies the work is done, fixed, ready to
  commit, ready for a PR, or passing.
- Writing or reviewing behavior tests for any change or flaky test.
- Turning an agreed spec, model, or root cause into acceptance criteria and
  checks.

## When NOT to Use

- Edits that change no behavior: formatting, typos, comments, and renames or
  moves that tooling confirms.
- A bug whose cause is not pinned down: `debugging` first.
- Design, naming, structure: `code-review`. Benchmarks: `performance`. Test
  runner setup: `scaffolding`.

## Rules

1. Anything else you report as true, such as a root cause, an invariant, or
   unchanged behavior, also needs a check. Report anything without one as
   `unproven` and name the missing evidence.
2. A bug fix needs a regression test that fails before the fix, passes
   after, and stays in the suite. A refactor needs the same checks passing
   before and after.
3. Each test asserts a business rule from the acceptance criteria or spec,
   with expected values taken from there, not from the code. A test that
   would still pass if the rule were wrong proves nothing, such as one that
   checks only for no error, a 200, or that a field exists. For each rule,
   choose the level that shows it most directly (unit for pure domain logic,
   integration for real dependencies, black-box for behavior across the
   system) and say why.
4. Use the real code a test calls; mock only the network and filesystem, or
   write down why. Fix the clock, random values, and generated IDs so the
   same input gives the same output. Do not test the framework or the
   language.
5. Fix a flaky test at its cause, never with sleeps or retries.
6. See each new test fail once for the right reason. If you wrote it before
   the code, run it first; if after, revert or break the change and run it.
   A test you have never seen fail may not test anything.
7. Check config, generated files, and docs by loading or running them the
   way the system does, never by asserting their text.
8. For a removal, test what remains and search to confirm the old code is
   gone. Test the removal itself only if callers now get an explicit error,
   such as a 404 or 410.
9. Before editing, run the existing tests for the code you will change.
   Never edit, skip, weaken, or delete a test, golden file, or snapshot to
   make the change pass. If one fails, fix the change, get the user's
   approval for the behavior change, or replace a test of internals with a
   test of the same rule and say so.
10. Work outward from one test: get it green, then run the other tests for
    the same code, then the tests for code the change could affect. Run the
    whole suite last, before saying done or committing. Report a failure
    unrelated to the change separately; it does not block.
11. Before saying done, re-read the latest request and corrections, look at
    each changed file as it is now, and rerun the checks. List each
    acceptance criterion with its check and result: proven, partly proven,
    blocked, or unproven.

## Tripwires

| Trigger | Do this instead | False alarm |
|---|---|---|
| "The suite is green, so it's done" | Name the acceptance criterion each passing test proves. | Every criterion already maps to a passing check. |
| "Add a unit test for every helper" | Test each business rule at the level that shows it most directly (Rule 3). | The helper is pure domain logic reached through its module's public functions. |
| "Update the test or snapshot so it passes" | Fix the change, or get the user's approval for the behavior change. | The test checks internals; replace it with a test of the same rule. |
| "The types already prove it" | Test the rule the types do not enforce. | The criterion is exactly what the type checker enforces. |
| "There's no way to test this, so skip proof" | Run it by hand and record the command, the output, and the criterion it proves. | An existing check already loads or runs it. |
| "The test mentions the changed code, so it counts" | Ask whether it would fail if the rule were wrong; rewrite it if not. | It fails when the rule is broken. |
| "The test passed first time" | Revert or break the change and watch it fail (Rule 6). | You saw it fail before the code existed. |

## Handoffs

- `specify`: acceptance criteria from an agreed design.
- `domain-modeling`: invariants that make invalid states unrepresentable.
- `debugging`: proof that hinges on root-cause evidence.
- `api`: tests of a public API contract.
- `refactoring`: before/after evidence, and tests that are hard to place
  because the code is tangled.
- `error-handling`: an unsettled error shape the proof must assert.
- `security`: abuse cases or trust-boundary checks.

## References

- `references/black-box.md`: load when choosing test inputs or outputs, or
  writing a black-box or integration test, a golden file, or a bug's
  regression guard.
- `references/data-shape-boundaries.md`: load when placing checks in
  pipelines, parsers, validators, middleware, or functional-core splits.
- `references/recipes.md`: load when the right check depends on the domain.
- `references/removals.md`: load for removals and replacements.
- `references/test-theater.md`: load when a test asserts how the code is
  built instead of what it does.
