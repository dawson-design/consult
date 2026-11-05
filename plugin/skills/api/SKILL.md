---
name: api
description: "House rules for HTTP APIs: spec first, compatibility for shipped consumers, status codes by where the failure starts, error format, idempotency, pagination, and webhooks. Use when adding or changing an endpoint, handler, status code, response or error body, or pagination."
---

# API

## Iron law

Write the OpenAPI spec first, keep shipped consumers working, and pick the
status by where the failure starts.

## Rules

1. Sketch the consumer-visible behavior in the OpenAPI spec (or the repo's
   API spec) before writing the handler, then build from it. List every
   response: success, errors, empty results, pagination, and auth failures.
   A fix that restores existing behavior follows the current contract.
2. Keep shipped contracts working for consumers you can't update in the same
   release, such as installed apps and open browser tabs. A rename, removal,
   required addition, status change, or change in meaning needs a successor
   (new field, endpoint, or version) or a deprecation window announced with
   `Deprecation` (RFC 9745) and `Sunset` (RFC 8594) headers. Optional
   additions old consumers can ignore change in place. Use one versioning
   scheme per service, and don't bump it for compatible additions.
3. Pick the status by where the failure starts. Map dependency failures into
   this API's own error shape; don't pass an upstream status or body through.

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

4. Keep an existing service's representation and error contract. A new REST
   resource API with no established format defaults to JSON:API, unless a
   domain standard or client need favors another documented choice. Errors
   use the chosen format's native shape, else RFC 9457 Problem Details.
   Don't claim conformance to a standard the API doesn't meet.
5. Middleware is for transport-wide concerns: logging, tracing, rate limits.
   Endpoint validation, ownership checks, authorization, and domain
   invariants stay at the route or domain boundary.
6. An endpoint that accepts retried mutations, returns a paginated list, or
   sends webhooks meets the floor in the matching reference below. Read it
   before writing the handler.

## References

- `references/idempotency.md`: read before writing a mutation clients retry.
- `references/pagination.md`: read before writing a paginated list.
- `references/webhooks.md`: read before sending or receiving webhooks.
- `references/rest-error-status-codes.md`: read when a status is not in the
  Rule 3 table, or one response must report several failures.
