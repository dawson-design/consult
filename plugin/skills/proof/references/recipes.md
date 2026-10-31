# Proof Recipes

Use these when the right check depends on the domain. Keep each acceptance
criterion, its check, and the done report aligned; do not run every recipe.

| Kind of change | Good evidence | Insufficient evidence |
|---|---|---|
| Behavior change | A check where the caller sees the result, plus tests of each business rule at the level that shows it (`proof` Rule 3), and the command run after the final edit. | Helper-only assertion, stale test output, or a passing unrelated suite. |
| Bug fix/root cause | Reproduced failure or described root cause. A regression check at the outermost boundary that reproduces the bug. It fails before, passes after, and stays as a guard. Final command output. | Guessing at a cause, patching symptoms, or relying on manual inspection alone when a check is practical. |
| Refactor preservation | Before/after behavior check at the same boundary, or focused characterization tests around the moved behavior. | "No behavior change" stated without evidence, or tests that only cover new helper internals. |
| Security/trust boundary | Negative abuse case, allowed-case check, and inspection of the input boundary, sink, logging, and auth/authz decision. | Lint/type checks, happy-path auth tests only, or a guard whose bypass cases were not exercised. |
| Database/migration | Migration apply/rollback or dry-run evidence, relevant query plan or constraint validation, and production rollout/rollback note when data is live. | SQL syntax inspection only, local tests without migration execution, or an index or constraint without database acceptance evidence. |
| Public API contract | Request/response or contract test for success and error cases, stable schema/status assertions, and compatibility note when callers exist. | Unit test below the transport layer only, snapshot drift without intent, or undocumented wire changes. |
| Accessibility/UI flow | Keyboard path, focus behavior, accessible names/status updates, contrast/reflow checks, and automated tooling where available. | Visual screenshot only, mouse-only manual pass, or automated tooling without keyboard/focus inspection. |
| Async/background work | Deterministic check for ordering, retry/cancellation/backpressure/concurrency limits, and observable lifecycle events. | Sleep-based timing, single happy-path task, or logs without assertions about failure behavior. |
| Release/rollback readiness | Version/changelog or rollout note, preflight/rollback verification, and named human decision points for shared environments. | "CI will catch it", release notes without rollback, or deploy steps that mutate shared state without approval. |
