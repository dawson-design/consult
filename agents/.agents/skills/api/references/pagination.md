# Pagination

Use this file when designing or changing list or stream endpoints.

## Page Size

- Cap the page size on the server even when the client asks for more, and
  document the cap and what an over-cap request gets.
- Adding paging params to a shipped unpaged list is compatible only if a
  call without them still returns the full list. Never let it silently
  become paged.

## Continuation Tokens

Prefer opaque cursors to page numbers. Page numbers suit only small, static
datasets, not streams, infinite scroll, or data that changes during a
session.

- **Opaque.** Clients never parse or build tokens.
- **Self-contained.** The token carries the state needed to resume,
  including its filters and sort, unless the contract requires clients to
  resend the same filters on every page.
- **Tamper-evident.** Sign the token, so a forged one cannot move the cursor
  into another consumer's data.
- **Versioned.** Put a format version in the token, so the server can reject
  tokens it no longer understands.

## Ordering

Order by a deterministic key with a unique tiebreaker, such as created-at
plus id, and keep that key in the resource so a cursor can resume from it.
Document the order. Changing it is a semantic change that needs a successor
contract.

## Invalid Tokens

Fail explicitly, and never fall back to the first page or an earlier
position:

| Token | Response |
|---|---|
| Malformed or tampered | `400`, without saying which check failed. |
| Expired | `400`, or a documented empty result with a link to restart. |
| Past the end | An empty page with no `next` token. |
