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
