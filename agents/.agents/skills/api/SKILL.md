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
- Database schema; use `database`.
- gRPC, GraphQL, or message-queue APIs: use `architecture` for the style
  decision and that ecosystem's conventions for the contract.

## Rules

1. Sketch consumer-visible behavior in the OpenAPI spec (or the repo's API
   spec) before writing handler code, then build from it. List every response:
   success, errors, empty results, pagination, and auth failures. A fix that
   restores existing behavior follows the current contract. Changes consumers
   depend on need approval through `contract-first`; additions old consumers
   cannot notice go ahead and are named in the close-out.
2. Keep shipped contracts working for independent consumers, ones you cannot
   update in the same release, such as installed apps and open browser tabs.
   Renames, removals, required additions, status-code changes, and changes in
   meaning to a shipped contract need a successor (a new field, endpoint, or
   version) or a deprecation path with an overlap window. Optional fields,
   params, headers, methods, and endpoints old consumers can ignore may
   change in place, as may a contract marked unstable or one no running
   consumer can see. Use one versioning scheme per service, and never bump it
   for compatible additions. Announce a deprecation with the `Deprecation`
   (RFC 9745) and `Sunset` (RFC 8594) response headers.
3. Pick the status by where the failure starts. Map dependency failures into
   this API's own error shape; never pass an upstream status or body through.

   | Failure | Status |
   |---|---|
   | Malformed syntax, envelope, or media type | `400` |
   | Well-formed input that breaks a domain rule | `422` |
   | Not authenticated | `401` |
   | Authenticated but not allowed | `403`, or `404` to hide that it exists |
   | No resource with that id (an empty collection is `200`) | `404` |
   | Conflicts with current state, such as a unique key | `409` |
   | Rate or quota exceeded | `429` |
   | A dependency is down or overloaded | `503` |
   | A dependency timed out | `504` |
   | A dependency answered with something unusable | `502` |
   | Unexpected fault in this service | `500` |

4. Preserve an existing service's representation and error contract. For a new
   REST resource API with no established format, default to JSON:API unless a
   domain standard or client interoperability need favors another documented
   choice. New APIs use the chosen model's native error format; document
   deviations. A model with no native error format uses RFC 9457 Problem
   Details. Never claim conformance to a standard the API does not meet.
5. Middleware is for transport-wide concerns (logging, tracing, rate limits).
   Endpoint-specific validation, ownership checks, privileged authorization,
   and domain invariants stay at the route or domain boundary.
6. An endpoint that takes retried mutations, returns a paginated list, or
   sends webhooks meets the floor in `references/idempotency.md`,
   `references/pagination.md`, or `references/webhooks.md`. Load the one that
   applies before writing the handler.

## Handoffs

- `contract-first`: approval of API contracts consumers depend on.
- `proof`: test request-to-response behavior, including status codes, error
  envelopes, and pagination.
- `error-handling`: internal failure mapping, timeouts, retries behind the API.
- `release`: version bumps and release notes for a deprecation.

## References

Load only the one the feature needs:

- `references/rest-error-status-codes.md`: which codes each endpoint
  documents, and how to report several failures in one response.
