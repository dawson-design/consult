## Turn 1: request

# Customer Import Pipeline

Build `processCustomers(records)` in `src/pipeline.js`.

Each input record has fields:

- `name`: string
- `email`: string
- `phone`: string

Requirements:

- Normalize email to lowercase and trimmed.
- Normalize phone to E.164 (assume US: digits only, prefix with `+1` when
  the input has 10 digits).
- Drop duplicate records by normalized email; keep the first.
- Records whose phone cannot be normalized go into an `errors` array with
  a `reason` field describing why; they do not appear in `valid`.
- Return `{ valid, errors }`.

Add tests.

Do not add external dependencies.

Work in the provided repository. Do not add external dependencies.

## Turn 2: approve

Approved, including any interface, data shape, or migration you proposed.
Build it, using your recommended option for anything still open. If the work
is already finished, say so.

## Turn 3: continue

Approved. Continue. If the work is already finished, say so.
