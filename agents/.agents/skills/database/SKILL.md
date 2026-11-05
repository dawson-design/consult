---
name: database
description: "Production-data safety rules for migrations, schema changes, indexes, constraints, backfills, transactions, and locking. Use when writing or changing a migration, schema, index, query, or transaction."
---

# Database

## Iron law

Protect production data first: prove rollout, locking, and recovery before
the change ships.

## Rules

1. Data deletion and non-reversible backfills always need the user's
   approval, because a rollback can't undo them. An additive, easily
   reversed change to a development-stage schema goes ahead and is named in
   the report.
2. Ship destructive or tightening changes as separate deployable
   expand-contract phases: expand, migrate, verify, switch, contract.
3. Review the migration SQL and its lock behavior directly, not only the ORM
   code. Create indexes and constraints with the target engine's online
   mechanism. SQLite passing proves nothing about Postgres; check
   engine-specific DDL against the target engine. Skip the online mechanism
   only when table size and write rate are verified negligible, and record
   why.
4. Enforce every uniqueness invariant with a `UNIQUE`, `EXCLUDE`, composite,
   or partial constraint, because application checks race under
   concurrency.
5. Document rollback and backup or point-in-time-recovery coverage for the
   blast radius with the change.
6. Give each new foreign key and each known `WHERE`, `JOIN`, or `ORDER BY`
   predicate a supporting index in the same migration, or state why not.
   Batch backfills and make them resumable. When a state change and the
   event or job it publishes must not diverge, use a transactional outbox,
   not a dual write.

## References

- `references/online-ddl.md`: read before any DDL on a production table, or
  when configuring SQLite for concurrent writes.
