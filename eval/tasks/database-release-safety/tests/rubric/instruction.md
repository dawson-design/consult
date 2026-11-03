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

Approved within the request as written: anything it rules out stays out.
Use your recommended option for any choice it leaves open. If you have
finished, say so.

## Turn 3: continue

Approved within the request as written. Continue with anything still
unfinished. If you have finished, say so.
