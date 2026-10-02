---
name: database
description: Migrations, schema changes, indexes, queries, transactions, or locking. Load before writing them.
---

# Database

## Iron Law

`PROTECT PRODUCTION DATA FIRST: PROVE ROLLOUT, LOCKING, AND RECOVERY BEFORE CHANGE.`

## When to Use

- Schema design, migrations, indexes, query plans, isolation levels,
  connection pools, soft delete, N+1 fixes, online DDL, transactional
  outbox/CDC, or production data changes.

## When NOT to Use

- API contract design; use `api`.
- Rollout sequencing outside the database; pair with `release`.
- Cache freshness and invalidation; use `performance`.

## Rules

1. Destructive and hard-to-reverse database changes are the user's call.
   Schema and migration changes that other code or stored data binds to route
   through `contract-first`, which owns the approval scope. Data deletion and
   non-reversible backfills always need explicit approval, because a rollback
   cannot undo them. An additive, easily reversed change on a
   development-stage schema proceeds with its shape stated in the close-out.
2. Use the project's existing database unless the task is choosing a store;
   `architecture` owns store selection.
3. Destructive or tightening changes ship as separate deployable
   expand-contract phases: expand, migrate, verify, switch, contract.
4. Review the migration SQL and its lock behavior directly, not just the ORM
   code. Index and constraint creation uses the target engine's online
   mechanism. SQLite passing is not proof of Postgres behavior; verify
   engine-specific DDL against the target engine.
5. Every uniqueness invariant is enforced by a DB-level `UNIQUE`, `EXCLUDE`,
   composite, or partial constraint, because application-layer checks race
   under concurrency.
6. New foreign keys and known `WHERE`, `JOIN`, or `ORDER BY` predicates get
   supporting indexes in the same migration, or a stated reason they do not.
   Important query changes include EXPLAIN/ANALYZE on production-shaped data.
7. Backfills are batched, resumable, observable, and reversible, and each
   batch holds locks briefly.
8. Isolation level and retry behavior are explicit for transactional changes.
   State changes and durable publication (events, jobs) share a transactional
   outbox, CDC, or equivalent when the two must not silently diverge.
9. Rollback and backup/PITR coverage for the blast radius are documented with
   the change.

## Tripwires

| Trigger | Do this instead | False alarm |
|---|---|---|
| "The table is small, ALTER it in place" | Use the engine's online mechanism, or record why size and write rate cannot matter. | Size and write rate are verified negligible and the reasoning is recorded. |
| "The migration will be quick" | Measure lock behavior on representative load or assume the worst case. | None. |
| "We can backfill later" | Ship the backfill plan now or leave the schema expand-only. | None. |
| "The app already checks uniqueness" | Enforce it with a DB constraint. | The invariant is advisory and duplicates are explicitly acceptable. |
| "Add the index when it gets slow" | Add supporting indexes in the same migration. | The access path is speculative and the omission is justified in the migration. |
| "This index looks unused, drop it" | Observe a full traffic cycle first. | The table itself is being removed. |
| "It's just another column" | Load `security` before adding password, token, API key, MFA, recovery-code, or sensitive-PII storage. | The column holds no credentials or sensitive data. |

## Handoffs

- `contract-first`: schema and migration approval.
- `release`: deploy ordering, rollback rehearsal, feature flags.
- `performance`: measured query latency or throughput change.
- `observability`: migration and query dashboards and alerts.
- `async-systems`: stream or worker consumers after durable handoff.
- `security`: credentials, secrets, tokens, MFA factors, sensitive PII.

## References

- `references/online-ddl.md`: load before any DDL on a production table.
- `references/explain-and-isolation.md`: load when reading a query plan or
  choosing an isolation level.
