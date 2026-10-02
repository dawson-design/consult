---
name: proof
description: "Writing or changing tests, or proving a change works: edge cases, invariants, behavior specs, evidence."
---

# Proof

## Iron Law

`NO ENGINEERING CLAIM WITHOUT A NAMED PROOF.`

A proof is a named check that would fail if the claim were false. "The tests
pass" does not count until you can say which test would break if you were
wrong.

## When to Use

- As the completion gate before any reply that says or implies the work is
  done, fixed, ready to commit, ready for a PR, or passing.
- Writing or reviewing behavior tests for any change or flaky test.
- Turning an agreed spec, model, contract, or root cause into Proof
  Contracts and runnable checks.

## When NOT to Use

- Edits with no behavior surface: formatting, typos, comments, renames and
  moves that tooling already confirms.
- A bug whose cause is not pinned down: `debugging` first.
- Design, naming, structure: `code-review`. Benchmarks: `performance`. Test
  runner setup: `scaffolding`.

## Rules

1. Every non-trivial claim owes a check. If you cannot point to one, mark the
   claim `unproven` and say which evidence is missing. Silence is not proof.
2. Match the proof to the claim: a behavior change needs a runnable check at
   the boundary, a new endpoint a contract test, a bug fix a regression test
   that fails before and passes after, a refactor the same behavior before
   and after, a data claim an invariant.
3. Test at boundaries, in the caller's words: where the data's shape, value,
   state, or error visibly changes, and always at the outermost boundary the
   caller sees (endpoint, CLI, UI, public API). Boundary tests survive
   refactors; unit-test only non-trivial pure logic.
4. One behavior per test. Real collaborators inside; mock only true system
   edges (network, clock, filesystem) or write the reason. Never test the
   framework, the language, or static text.
5. A flaky test is a bug in the test, the code, or the environment. Fix it.
   No sleeps, no retries.
6. Red before green when the failing test is itself the evidence: a
   reproducible bug, a behavior change with a clear observable, a contract
   change. A test that passes on its first run proves nothing; verify the red
   as deliberately as the green.
7. Prove artifacts the way the system uses them: run, load, parse, render, or
   inspect config, wiring, generated output, and documents. Never assert
   literal text.
8. For a removal, prove the behavior that remains and confirm the old code is
   gone with a search. Test the removal itself only when it now returns an
   explicit rejection (404, 410, deprecation error): that is new behavior.
9. Narrowest check first: one test by name or line, then the file. Once a
   failing test is known, iterate on that failure until it is green. Run the
   whole package or suite after major changes, before completion or commit,
   or when targeted green evidence suggests wider breakage. An unrelated broad
   failure is reported separately, not treated as blocking.
10. "Done" is a claim. Before saying it: re-read the latest request and any
    corrections, look at every named file as it stands after your last edit,
    run the chosen check fresh, and report proven, partly proven, blocked, or
    unproven. Smoke and helper-only checks are partial, not acceptance.

### Proof Contract

Fill these five fields for each non-trivial claim. Other skills hand work
here expecting them.

- **Claim**: the behavior, invariant, contract, or root cause you assert.
- **Data invariant**: the shape, state rule, or type that makes bad states
  impossible, or at least visible.
- **Boundary**: where the claim becomes observable, so where the check enters.
- **Check**: the runnable test or command that would fail if the claim were
  false.
- **Evidence**: the command and output, the test name and result, the
  artifact inspected, or why you could not run it.

## Tripwires

| Trigger | Do this instead | False alarm |
|---|---|---|
| "The suite is green, so the change is proven" | Run the check that would fail if this change were wrong; a green check that never touches the change is partial. | The green check enters at the changed boundary. |
| "Run the whole suite for this one-line edit" | Run the relevant test or file first; widen after major changes, before commit, or when wider breakage is plausible. | The change is cross-cutting and no narrower check exists. |
| "Add a unit test for every helper" | Test the contract at the boundary. | The helper has branching or state a boundary test cannot drive. |
| "The types already prove it" | Check the invariant or behavior the types do not cover. | The claim is exactly what the type checker enforces. |
| "There's no way to test this, so skip proof" | Record the manual check: command, output, and the claim it proves. | An existing check already loads or runs the artifact. |
| "The test mentions the changed code, so it counts" | Rewrite or delete tests that assert how the code is built instead of what it does. | The asserted structure is itself a public contract. |

## Handoffs

- `specify`: an agreed design artifact's proof obligations.
- `domain-modeling`: invariants that make invalid states unrepresentable.
- `debugging`: proof that hinges on root-cause evidence.
- `api`: claims that are public contracts.
- `refactoring`: before/after evidence, and tests that are hard to place
  because the code is tangled.
- `error-handling`: an unsettled error shape the proof must assert.
- `security`: abuse cases or trust-boundary checks.

## References

- `references/data-shape-boundaries.md`: load when placing checks in
  pipelines, parsers, validators, middleware, or functional-core splits.
- `references/recipes.md`: load when the proof shape is domain-specific.
- `references/removals.md`: load for removals and replacements.
- `references/test-theater.md`: load when a test asserts how the code is
  built instead of what it does.
- The Pi `/proof` command runs a red-green cycle; its output counts only
  toward the claims it covers.
