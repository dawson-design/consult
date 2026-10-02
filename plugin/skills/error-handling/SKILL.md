---
name: error-handling
description: "How code fails: error types, error messages and responses, validation errors, retries. Load before editing."
---

# Error Handling

## Iron Law

`ERRORS CARRY CONTEXT. NEVER CATCH WITHOUT HANDLING OR RE-RAISING.`

## When to Use

- Designing or reviewing typed errors, Result/Either flows, domain error
  boundaries, wrapping, retries, remote-call failures, panics, user-facing
  errors, or swallowed failures.

## When NOT to Use

- Security-specific failure shape; pair with `security`.
- REST status codes or public API error schema; use `api`.
- Error visibility in production; pair with `observability`.

## Rules

1. Failure is part of the function contract. Expected failures are typed
   (named exception classes, discriminated unions, structured `Result`
   variants), never bare strings or anonymous generic errors.
2. Catch only where you can decide: recover, translate, retry, or terminate.
   Every catch does one of those or re-raises with context, preserving the
   original cause.
3. Translate at boundaries. Domain, infrastructure, API, CLI, and UI errors do
   not leak across a boundary unchanged.
4. Remote calls declare timeout, retry, idempotency, and dependency-failure
   behavior (circuit breaker, bulkhead, load shedding, or fail fast)
   together, before the caller is written. Retries apply only to idempotent
   transient failures, in one layer, with a capped budget and jittered
   backoff. Two retrying layers multiply load on a failing dependency.
5. User-facing errors are actionable and expose no stack traces, SQL, file
   paths, hostnames, secrets, or auth-enumeration clues. Diagnostic detail
   stays reachable by correlation ID.
6. Panics and assertions are for impossible states and process boundaries,
   not routine control flow.
7. Every public operation that can fail has at least one failure-path test.

## Tripwires

| Trigger | Do this instead | False alarm |
|---|---|---|
| "Log and continue is fine" | Decide: recover, translate, retry, or terminate. | Best-effort telemetry with an explicit drop policy. |
| "This can't fail in practice" | Declare the failure-capable contract and test a representative failure. | The state is impossible by type or value construction. |
| "Swallow at the boundary" | Translate for the caller and preserve the cause for diagnostics. | A security boundary deliberately hides details while logging a correlation ID. |
| "We'll add remote-call protection later" | Define timeout, retry budget, idempotency guard, and dependency-failure behavior now. | Local in-memory call with no blocking I/O. |

## Handoffs

- `security`: fail-closed behavior and information disclosure.
- `api`: status codes, Problem Details or JSON:API error contracts.
- `domain-modeling`: an error vocabulary that is part of the domain model.
- `observability`: correlation IDs, error-rate alerts, dependency health.
- `async-systems`: retry semantics for jobs and stream consumers.

## References

- `../api/references/rest-error-status-codes.md`: load when the error
  surfaces through a REST boundary.
