# Idempotency

Use this file when a public mutation must be safe to retry.

## Idempotency-Key Contract

Document each of these for every retryable mutation, in the OpenAPI spec
and the SDK docs:

- **Key scope.** Which requests share a key namespace: per account, per API
  key, per endpoint, or global.
- **Replay window.** How long the server keeps the keyed response. After it
  elapses, the same key runs as a fresh request.
- **Duplicate behavior.** What a repeat of the same key and body returns,
  usually the stored original response.
- **Conflict behavior.** What the same key with a different body returns,
  and what a repeat returns while the first request is still in flight.

## Server Floor

- Store the key with a hash of the request, the response, and the status,
  within its scope.
- Claim the key atomically before running the mutation, so two concurrent
  requests with one key cannot both run it.
- Compare the request hash before replaying, and reject a mismatch with the
  documented conflict status.

## Client Floor

- Generate the key once per logical operation, before the first attempt,
  and reuse it on every retry of that operation.
- Log the key so duplicate attempts can be traced.

`GET`, `HEAD`, `OPTIONS`, `PUT` that sets whole state, and `DELETE` are
idempotent by HTTP semantics and need no key. Say so in the contract, so
consumers know which mutations are safe to retry.
