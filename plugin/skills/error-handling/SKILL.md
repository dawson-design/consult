---
name: error-handling
description: "How code fails: error types, error messages and responses, validation errors, retries. Load before editing."
---

# Error Handling

## Iron Law

`ERRORS CARRY CONTEXT. NEVER CATCH WITHOUT HANDLING OR RE-RAISING.`

## When to Use

- Designing or reviewing typed errors, Result/Either flows, domain error
  boundaries, wrapping, retries, remote-call failures, user-facing
  errors, or swallowed failures.

## When NOT to Use

- Security-specific failure behavior; pair with `security`.
- REST status codes or public API error schema; use `api`.
- Error visibility in production; pair with `observability`.

## Rules

1. Failure is part of the function contract. Expected failures are typed.
   Follow the project's convention (named exception classes, discriminated
   unions); where it has none, return Result-style values, because the
   caller's type then shows every way the call can fail. Never bare strings
   or anonymous generic errors.
2. Catch only where you can decide: recover, translate, retry, or terminate.
   Every catch does one of those or re-raises with context, preserving the
   original cause. Best-effort telemetry with an explicit drop policy may log
   and continue.
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
6. Every public operation that can fail has at least one failure-path test.

## Handoffs

- `security`: fail-closed behavior and information disclosure.
- `api`: status codes, Problem Details or JSON:API error contracts.
- `domain-modeling`: an error vocabulary that is part of the domain model.
- `observability`: correlation IDs, error-rate alerts, dependency health.
- `async-systems`: retry semantics for jobs and stream consumers.

## References

- `../api/references/rest-error-status-codes.md`: load when the error
  surfaces through a REST boundary.
