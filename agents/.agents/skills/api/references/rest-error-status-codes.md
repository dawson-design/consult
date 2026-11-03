# REST Error Status Codes

Use this file to decide which status codes each REST endpoint documents, and
how to report several failures in one response. `api` Rule 3 says which code
a given failure returns.

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

## Several Failures in One Request

- Return all actionable request errors together, each pointing at the input
  it rejects.
- When those errors carry different `4xx` statuses, follow the operation's
  documented choice: the most specific status, or `400` with per-field
  details.
- Never report a client failure and a service or upstream failure together
  as a client error.
