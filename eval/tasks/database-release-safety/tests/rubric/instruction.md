## Turn 1: request

# Customer Email Migration

Update the migration files for adding a customer email lookup.

Target engine: PostgreSQL.

Requirements:

- Add customer email lookup support in a way suitable for a large live
  PostgreSQL table.
- Normal writes must continue during rollout.
- The uniqueness rule needs a separately validated path and must be valid
  PostgreSQL.
- Include rollback and operator notes for rollout, validation, and failure.

Do not add external dependencies.

Work in the provided repository. Do not add external dependencies.

## Turn 2: approve

Approved, including any interface, data shape, or migration you proposed.
Build it, using your recommended option for anything still open. If the work
is already finished, say so.

## Turn 3: continue

Approved. Continue. If the work is already finished, say so.
