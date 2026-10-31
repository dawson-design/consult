# Pagination

Use this reference when designing list or stream endpoints.

## Rule

List and stream endpoints have bounded pagination, stable ordering,
and explicit continuation-token semantics. Opaque cursors, page
tokens, sync tokens, and resume tokens are consumer input: malformed,
tampered, expired, or out-of-range tokens fail with a documented
client error or empty-result behavior, never a silent fallback to an
earlier position.

## Page Size

- Cap results server-side (`max_page_size`) even when the client
  passes a larger value. Document the cap.
- Default page size matches the most common use; expose a `limit`
  parameter for consumers that need a different size up to the cap.

## Continuation Tokens

Prefer opaque cursors over page numbers:

- **Opaque to clients.** The token is a sealed string the server
  produces and consumes. Clients must not parse or construct them.
- **Self-contained.** The token carries enough state to resume
  deterministically; do not depend on stable client-side filters
  being passed unchanged on every request unless the contract
  documents that.
- **Tamper-evident.** Sign or HMAC the token so a forged token
  cannot reposition the cursor into another consumer's data.
- **Versioned.** Include a small format version inside the token so
  the server can reject tokens it can no longer interpret.

Page numbers (`?page=N`) are acceptable for static, small datasets
but not for streams, infinite scroll, or anything that changes during
the session.

## Ordering

- Pick a deterministic order key (created-at + tiebreaker id is
  common). The order key must be in the resource projection so
  cursors can be resumed deterministically.
- Document the order; do not change it without a successor contract.

## Invalid-Token Behavior

When the server cannot interpret a continuation token, fail
explicitly:

- Malformed → `400 Bad Request`.
- Tamper-detected → `400 Bad Request` (avoid leaking detection logic).
- Expired → `400 Bad Request`, or document an empty-result with a
  `Link: rel="first"` to restart.
- Out-of-range → empty result with `next` token absent, or `400` if
  the range is impossible.

Never silently fall back to the first page or an earlier position.
