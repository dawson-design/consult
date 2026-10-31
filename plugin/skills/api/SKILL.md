---
name: api
description: Adding or changing an HTTP endpoint, handler, status code, response or error body, or pagination. Load before editing.
---

# API

## Iron Law

`WRITE THE OPENAPI SPEC FIRST. PRESERVE SHIPPED CONSUMERS. PICK STATUS BY FAILURE.`

## When to Use

- Adding, removing, renaming, or reviewing REST endpoints, fields, status
  codes, webhooks, auth, pagination, rate limits, or idempotency.
- Writing or changing an HTTP API's OpenAPI spec or JSON Schema.

## When NOT to Use

- Internal function signatures with no caller contract; use `domain-modeling`.
- Auth, secrets, or trust-boundary review beyond the API contract; use `security`.
- Database schema; use `database`.
- gRPC, GraphQL, or message-queue APIs: use `architecture` for the style
  decision and that ecosystem's conventions for the contract.

## Rules

1. Sketch new or changed behavior consumers can see in the OpenAPI spec (or
   the repo's API spec) before writing handler code, then build from it. Spell
   out every response, including success, errors, empty results, pagination,
   and auth failures. For a fix that restores existing behavior, the current
   contract is the source of truth. Changes to endpoints consumers depend on
   get approval through `contract-first`. Additions old consumers cannot
   notice (a new optional field, param, or endpoint) go ahead; describe them
   in the close-out.
2. Don't break a shipped contract that has independent consumers: ones you
   cannot update in the same release, such as open browser tabs and installed
   apps still running old code. Optional fields, params, headers, methods, and
   endpoints may change in place when old consumers can ignore them. Renames,
   removals, required additions, status-code changes, and changes in meaning
   to a shipped contract need a successor (such as a new field, endpoint, or
   version) or a deprecation path with an overlap window. A contract marked
   unstable, or one whose change no running consumer can see, may change in
   place. Use one versioning scheme per service, and never bump it for
   compatible additions.
3. Use `4xx` for consumer-side conditions such as invalid input, missing
   resources, authorization, or rate limits; use `5xx` when this service or a
   dependency cannot fulfill a valid request.
   Never mix origins in one response or leak raw upstream or internal errors.
4. Preserve an existing service's representation and error contract. For a new
   REST resource API with no established format, default to JSON:API unless a
   domain standard or client interoperability need favors another documented
   choice. New APIs use the chosen model's native error format; document
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
| "Renaming this field is harmless" | Keep shipped consumers working with a successor or a deprecation path. | The field never shipped, or no running consumer can see the change. |
| "Any error can be a 400 (or a 500)" | Classify consumer-side conditions and service failures separately. | None. |
| "Return whatever the handler has" | Define response and error bodies in the spec first. | None. |
| "The list is small, skip pagination" | Define bounded pagination and invalid-token behavior before the endpoint can grow. | The collection is provably bounded, such as an enum-sized set. |
| "Consumers can just retry the mutation" | Define the idempotency contract first, or document the mutation as unsafe to retry. | The mutation is naturally idempotent and documented as such. |
| "It's just an outgoing webhook" | Sign, timestamp, replay-protect, version, and deduplicate. | Delivery stays inside one trust boundary. |
| "Put the check in middleware so it's global" | Keep route-specific validation, ownership, and domain rules in handler or domain code. | The concern is genuinely transport-wide. |

## Handoffs

- `contract-first`: approval of API contracts consumers depend on.
- `proof`: test request-to-response behavior, including status codes, error
  envelopes, and pagination.
- `error-handling`: internal failure mapping, timeouts, retries behind the API.
- `security`: authn/authz, input trust, SSRF, data exposure.
- `async-systems`: SSE, subscriptions, event streams.
- `release`: version bumps, `Sunset` and `Deprecation` headers.

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
