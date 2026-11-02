#!/bin/bash
# Oracle: three separately runnable phases for a large live PostgreSQL table.
# 001 adds a nullable column (a catalog-only change, guarded by lock_timeout),
# 002 builds the unique index CONCURRENTLY on its own, outside any transaction,
# and 003 attaches it as a UNIQUE constraint with USING INDEX, so no step scans
# the table under a write-blocking lock. Each phase has its own .down.sql, and
# the operator notes cover order, checks, failure, and rollback. No test is
# added: there is no PostgreSQL here, and asserting the SQL text proves
# nothing, so validity on PostgreSQL stays unproven in the report.
set -euo pipefail
cd /app

cat > migrations/001_customer_email.sql <<'SQL'
-- Phase 1 of 3: add the nullable email column.
-- A nullable column with no default only changes the catalog, so the
-- ACCESS EXCLUSIVE lock is held for milliseconds. lock_timeout makes the
-- statement give up instead of queueing writes behind a long transaction.
SET lock_timeout = '5s';
ALTER TABLE customers ADD COLUMN email text;
SQL

cat > migrations/001_customer_email.down.sql <<'SQL'
-- Rollback of phase 1. DESTROYS DATA: dropping the column deletes every email
-- written since phase 1. Run it only after the operator has decided to lose
-- that data and has a current backup. Roll back 003 and 002 first.
SET lock_timeout = '5s';
ALTER TABLE customers DROP COLUMN IF EXISTS email;
SQL

cat > migrations/002_customer_email_unique_index.sql <<'SQL'
-- Phase 2 of 3: build the unique index without blocking writes.
-- CREATE INDEX CONCURRENTLY cannot run inside a transaction block: run this
-- file on its own, with the migration runner's transaction wrapping off.
-- No IF NOT EXISTS, so an invalid index left by a failed build is not
-- mistaken for a finished one.
CREATE UNIQUE INDEX CONCURRENTLY customers_email_idx ON customers (email);
SQL

cat > migrations/002_customer_email_unique_index.down.sql <<'SQL'
-- Rollback of phase 2. Run outside a transaction block, like phase 2.
DROP INDEX CONCURRENTLY IF EXISTS customers_email_idx;
SQL

cat > migrations/003_customer_email_unique_constraint.sql <<'SQL'
-- Phase 3 of 3: attach the validated index as the uniqueness constraint.
-- USING INDEX reuses the index from phase 2, so there is no table scan; the
-- brief ACCESS EXCLUSIVE lock is bounded by lock_timeout. PostgreSQL renames
-- the index to customers_email_key.
SET lock_timeout = '5s';
ALTER TABLE customers ADD CONSTRAINT customers_email_key UNIQUE USING INDEX customers_email_idx;
SQL

cat > migrations/003_customer_email_unique_constraint.down.sql <<'SQL'
-- Rollback of phase 3. Dropping the constraint also drops its index, so email
-- lookups lose their index until phase 2 runs again.
SET lock_timeout = '5s';
ALTER TABLE customers DROP CONSTRAINT IF EXISTS customers_email_key;
SQL

cat > migrations/customer_email_rollout.md <<'MD'
# Customer email lookup: rollout notes

Adds `customers.email` (nullable `text`) with a unique index for lookups by
email, in three phases. Each phase is its own file and its own deploy step.
Normal reads and writes continue throughout.

| Phase | Forward | Rollback | Lock taken |
|---|---|---|---|
| 1 | `001_customer_email.sql` | `001_customer_email.down.sql` | ACCESS EXCLUSIVE for a catalog change, bounded by `lock_timeout` |
| 2 | `002_customer_email_unique_index.sql` | `002_customer_email_unique_index.down.sql` | SHARE UPDATE EXCLUSIVE (writes continue) |
| 3 | `003_customer_email_unique_constraint.sql` | `003_customer_email_unique_constraint.down.sql` | ACCESS EXCLUSIVE briefly, bounded by `lock_timeout`, no scan |

## Before you start

- Confirm a current backup or point-in-time recovery window covers `customers`.
- Decide whether emails are unique case-sensitively. This index treats
  `Ada@example.com` and `ada@example.com` as different. If they must clash,
  stop: that needs a `lower(email)` index, which cannot back a constraint.

## Rollout

Run the phases in order. Do not start a phase until the previous phase's
check passes.

1. Apply phase 1. Check:

   ```sql
   SELECT data_type, is_nullable FROM information_schema.columns
   WHERE table_name = 'customers' AND column_name = 'email';
   -- expect: text | YES
   ```

2. Before phase 2, check for duplicate emails written since phase 1:

   ```sql
   SELECT email, count(*) FROM customers
   WHERE email IS NOT NULL GROUP BY email HAVING count(*) > 1;
   -- expect: no rows
   ```

   If rows come back, stop and have the data owner resolve them. Do not
   delete rows to make the build pass.

3. Apply phase 2 outside a transaction block (for example
   `psql -f migrations/002_customer_email_unique_index.sql`), with
   `statement_timeout` off for that session. On a large table it can take a
   long time; follow it in `pg_stat_progress_create_index`. Check:

   ```sql
   SELECT indisvalid, indisready FROM pg_index
   WHERE indexrelid = 'customers_email_idx'::regclass;
   -- expect: t | t
   ```

4. Apply phase 3. Check:

   ```sql
   SELECT contype FROM pg_constraint
   WHERE conrelid = 'customers'::regclass AND conname = 'customers_email_key';
   -- expect: u
   EXPLAIN SELECT id FROM customers WHERE email = 'someone@example.com';
   -- expect: Index Scan using customers_email_key
   ```

## Failure

- Phase 1 or 3 fails with `canceling statement due to lock timeout`: nothing
  changed. Wait for the long transaction to finish and run the phase again.
- Phase 2 fails (a duplicate key, a cancel, a lost connection): PostgreSQL
  leaves an INVALID index named `customers_email_idx` that still slows writes
  and does not enforce uniqueness. Find it with the phase 2 check
  (`indisvalid = f`), drop it with `002_customer_email_unique_index.down.sql`,
  fix the cause (resolve duplicates through the data owner), then run phase 2
  again.
- Phase 3 fails because the index is invalid or missing: go back to phase 2.

## Rollback

Roll back newest phase first: 003, then 002, then 001.

- `003_..._constraint.down.sql` drops the constraint and its index. Lookups
  lose the index until phase 2 runs again.
- `002_..._unique_index.down.sql` drops the index; run it outside a
  transaction block.
- `001_customer_email.down.sql` drops the column and DESTROYS every email
  stored since phase 1. It is the operator's explicit decision, after a
  backup. Leaving the unused nullable column in place is usually safer.
MD
