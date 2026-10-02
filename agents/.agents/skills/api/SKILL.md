---
name: api
description: Adding or changing an HTTP endpoint, handler, status code, response or error body, or pagination. Load before editing.
---

# API

## Iron Law

`DEFINE THE CONTRACT FIRST. PRESERVE SHIPPED CALLERS. PICK STATUS BY FAILURE.`

## When to Use

- Adding, removing, renaming, or reviewing REST endpoints, fields, status
  codes, webhooks, auth, pagination, rate limits, or idempotency.
- Writing or changing OpenAPI, JSON Schema, public SDK boundaries, or
  integration contracts external callers depend on.

## When NOT to Use

- Internal function signatures with no caller contract; use `domain-modeling`.
- Auth, secrets, or trust-boundary review beyond API shape; use `security`.
- Database schema; use `database`.
- gRPC, GraphQL, or message-queue APIs: use `architecture` for the style
  decision and that ecosystem's conventions for shape.

## Rules

1. Sketch new or changed caller-visible behavior in OpenAPI or the repo's
   contract source before controller code, then implement from it. For a fix
   that restores existing behavior, use the current contract as the source of
   truth. Make every response shape explicit, including errors, empty states,
   pagination, and auth failures. Durable API interfaces route through
   `contract-first`. Additive changes old callers cannot notice (a new
   optional field, param, or endpoint) proceed without a stop; state the shape
   in the close-out.
2. Preserve shipped contracts with independent callers. Optional fields,
   params, headers, methods, and endpoints evolve in place when old callers
   can ignore them. When they alter a shipped contract, renames, removals,
   required additions, status-code changes, and semantic changes need a
   successor contract or a deprecation path with an overlap window. An
   explicitly unstable contract, or one whose change no running caller can
   observe, may change in place. Open browser tabs and installed apps are
   independent running callers. Use one versioning strategy per service;
   compatible additions never re-version.
3. Use `4xx` for caller-side conditions such as invalid input, missing
   resources, authorization, or rate limits; use `5xx` when this service or a
   dependency cannot fulfill a valid request.
   Never mix origins in one response or leak raw upstream or internal errors.
4. Preserve an existing service's representation and error contract. For a new
   REST resource API with no established format, default to JSON:API unless a
   domain standard or client interoperability need favors another documented
   choice. New APIs use the chosen model's native error shape; document
   deviations.
5. Non-idempotent mutations define idempotency key scope, replay window,
   duplicate response, and conflict semantics, or are documented as unsafe to
   retry.
6. Lists have bounded pagination, stable ordering, and explicit invalid-token
   behavior. A bad token never silently restarts, rewinds, or skips position.
7. External webhooks are signed, timestamped, replay-protected, versioned, and
   deduplicable.
8. Middleware is for transport-wide concerns (logging, tracing, rate limits).
   Endpoint-specific validation, ownership checks, privileged authorization,
   and domain invariants stay at the route or domain boundary.
9. Tests exercise the public boundary. Source-of-truth docs are updated, not
   generated output by hand.

## Tripwires

| Trigger | Do this instead | False alarm |
|---|---|---|
| "Renaming this field is harmless" | Preserve shipped callers with a successor contract or deprecation path. | The field never shipped, or no running caller can observe the change. |
| "Any error can be a 400 (or a 500)" | Classify caller-side conditions and service failures separately. | None. |
| "Return whatever the handler has" | Define response and error shape in the contract first. | None. |
| "The list is small, skip pagination" | Define bounded pagination and invalid-token behavior before the endpoint can grow. | The collection is provably bounded, such as an enum-sized set. |
| "Callers can just retry the mutation" | Define the idempotency contract first, or document the mutation as unsafe to retry. | The mutation is naturally idempotent and documented as such. |
| "It's just an outgoing webhook" | Sign, timestamp, replay-protect, version, and deduplicate. | Delivery stays inside one trust boundary. |
| "Put the check in middleware so it's global" | Keep route-specific validation, ownership, and domain rules in handler or domain code. | The concern is genuinely transport-wide. |

## Handoffs

- `contract-first`: durable API approval.
- `proof`: test request-to-response behavior, including status codes, error
  envelopes, and pagination.
- `error-handling`: internal failure mapping, timeouts, retries behind the API.
- `security`: authn/authz, input trust, SSRF, data exposure.
- `async-systems`: SSE, subscriptions, event streams.
- `release`: version bumps, `Sunset` and `Deprecation` primitives.

## References

Load only the one the feature needs:

- `references/api-evolution.md`: evolution rules and versioning strategies.
- `references/rest-error-status-codes.md`: status-by-origin decision tree.
- `references/data-models.md`: JSON:API default; FHIR, HAL, JSON-LD.
- `references/idempotency.md`: idempotency-key contract.
- `references/pagination.md`: cursor and bounded-pagination semantics.
- `references/webhooks.md`: signing, versioning, replay protection.
- `references/middleware-vs-handler.md`: request-pipeline placement.
- `../security/references/web-app.md`: CSRF middleware, security headers, CORS.
- `../security/references/api-and-auth.md`: handler-level authorization for
  privileged endpoints.
