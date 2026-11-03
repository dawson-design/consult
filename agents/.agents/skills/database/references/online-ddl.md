# Online DDL

Use this file before DDL or a backfill on a table that keeps serving traffic,
or when configuring SQLite for concurrent writes. The supported defaults are
Postgres and SQLite.

## Postgres

- Set a short `lock_timeout` (such as `2s`) before DDL, and retry the DDL in
  a loop with a small lock window, as GitLab's `with_lock_retries` does. DDL
  waiting for its lock blocks every later query on the table, and a bare
  timeout only fails the deploy.
- `CREATE INDEX CONCURRENTLY` and `DROP INDEX CONCURRENTLY` cannot run inside
  a transaction, so turn off the migration tool's wrapping transaction for
  that step. A failed concurrent build leaves an `INVALID` index; drop it
  before retrying.
- Add foreign keys and `CHECK` constraints as `NOT VALID`, then
  `VALIDATE CONSTRAINT` in a separate step, so the scan holds only a share
  lock. To make a large column `NOT NULL`, validate a
  `CHECK (c IS NOT NULL)` first; `SET NOT NULL` then skips the full scan.
- Backfill in key-range batches, each in its own transaction, so a rerun
  resumes from the last finished batch instead of one long `UPDATE`.
- Before dropping an index that shows zero scans, observe a full traffic
  cycle, and keep unique indexes: they enforce uniqueness without counting
  as scans.

## SQLite

- DDL locks the whole database. Keep migrations short, and run large
  rewrites in a maintenance window.
- A table rebuild (create the new table, copy, swap) loses writes made
  during the copy unless writes stop first. Run it in one transaction or in
  a maintenance window, never as a batched copy under live traffic.
- SQLite allows one writer at a time. Enable WAL
  (`PRAGMA journal_mode = WAL;`) for concurrent readers, and set
  `busy_timeout` so brief contention waits instead of failing.
- Open write transactions with `BEGIN IMMEDIATE`. A deferred transaction
  that reads and then writes can fail with `SQLITE_BUSY` despite the
  timeout.
- Multiple independent writers, such as several app servers or background
  jobs, call for Postgres. That store change is an `architecture` decision.
