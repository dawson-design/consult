# REST Error Status Codes

Use this file to decide which status codes each REST endpoint documents, and
which code a given error returns. Choose by whether the failure is a
consumer-side condition or a valid request failed in the service or a
dependency. Then translate to a stable public error contract. Never pass raw
upstream or internal errors through to consumers.

## Codes Each Endpoint Documents

Document every status code the endpoint can return, and no others. A code
listed on an endpoint that cannot produce it hides the codes that matter.

| If the endpoint... | It documents |
|---|---|
| Always | One success code chosen by method: `200` with a body, `201` for a create, `202` for accepted async work, `204` with no body. |
| Accepts input (body, query, path, or headers) | `400`, plus `422` when domain rules can reject well-formed input. |
| Requires authentication | `401` with a `WWW-Authenticate` header. |
| Applies permissions or ownership | `403`, or `404` when the resource's existence must stay hidden from this consumer. |
| Addresses a resource by id | `404`. A collection endpoint returns an empty list, not `404`. |
| Can conflict with current state (unique keys, versions, idempotency replays) | `409`. |
| Enforces a rate or quota limit | `429`. |
| Can refuse work itself (maintenance, load shedding, an open circuit breaker) or calls an upstream service | `503`. |
| Calls an upstream service | `502`, `504`. |

Define `500` once for the whole API, as the OpenAPI `default` response or a
shared entry in `components/responses`, instead of repeating it on every
endpoint. Do the same for codes a gateway or platform can return on any route.

## Request-Origin Errors

Use `4xx` for consumer-side conditions such as invalid input, missing resources,
authorization, or rate limits.

- `401 Unauthorized`: the consumer is not authenticated or the credentials are
  missing, expired, malformed, or invalid.
- `403 Forbidden`: the consumer is authenticated but is not allowed to perform
  the action or access the resource.
- `429 Too Many Requests`: the consumer exceeded a documented rate or quota
  limit.
- `404 Not Found`: the requested resource does not exist or must not be
  disclosed to this consumer.
- `400 Bad Request`: the request syntax, envelope, query syntax, media type, or
  general request shape is malformed.
- `422 Unprocessable Entity`: the request is syntactically valid, but one or
  more values violate domain rules.

Return all actionable request errors together when practical. If multiple
request errors have different specific `4xx` statuses, use the documented API
contract for that operation: either the most specific status or a generic `400`
with per-field details. Do not report client and server-origin failures together
as a client error.

## Upstream-Origin Errors

Use `5xx` gateway-style statuses when your API depends on another service and
the dependency prevents your API from satisfying the request.

- `503 Service Unavailable`: the upstream service is unavailable, overloaded,
  down for maintenance, or cannot currently accept requests.
- `504 Gateway Timeout`: the upstream service did not respond within the timeout
  budget.
- `502 Bad Gateway`: the upstream service responded, but with an invalid,
  unusable, or failed response that your API cannot translate into success.

Always map upstream failures into your public error shape. Do not leak upstream
hostnames, stack traces, SQL, raw payloads, vendor-specific error bodies, or
other implementation details.

## Application-Origin Errors

Use `500 Internal Server Error` for unexpected faults in your API application or
its components after request and upstream causes have been ruled out.

At gateway, load-balancer, or platform boundaries, your own service being
unavailable may surface as `503`, and your own service timing out may surface as
`504`. Application code should still classify the underlying fault so logs,
metrics, traces, and correlation IDs can explain it.

## Response Shape

Use one consistent error schema per API matching the chosen data
model. JSON:API errors, RFC 9457 Problem Details, and FHIR
`OperationOutcome` are *structurally distinct conventions* with
different envelopes, field names, and types; they are not
interchangeable. Pick one per API; do not hybridize fields across
shapes.

See `data-models.md` for spec-correct fields per standard.

Whatever the chosen shape, the API contract should expose:

- A status indicator that matches the HTTP status code (string in
  JSON:API, integer in Problem Details).
- A stable, human-readable summary of the error class (JSON:API
  `title`; Problem Details `title`; FHIR `issue.code` + `details`).
- An occurrence-specific explanation in safe, actionable language
  (`detail` in JSON:API and Problem Details; `diagnostics` in FHIR).
- A way to point at the offending input (JSON:API `source.pointer`/
  `parameter`/`header`; FHIR `location` and `expression`; Problem
  Details extensions).
- A correlation handle linking the consumer-facing error to internal
  logs without leaking internals (JSON:API `id` or `meta`; Problem
  Details `instance` or extension; FHIR `id`).
