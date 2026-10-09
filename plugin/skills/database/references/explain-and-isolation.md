# EXPLAIN and transaction isolation

Deep reference for the `database` skill. How to read a query plan and how
isolation levels actually differ for the supported defaults: SQLite and
Postgres.

## Reading Postgres EXPLAIN

Run with `ANALYZE` + `BUFFERS` to get real numbers:

```sql
EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT) SELECT ...;
```

### Operators you meet daily

| Operator                      | What it does                                  | When it's a problem                                                       |
| ----------------------------- | --------------------------------------------- | ------------------------------------------------------------------------- |
| Seq Scan                      | Full table scan                               | Large table, low output row count → missing index                         |
| Index Scan                    | Walk the B-tree, fetch matching heap tuples   | Fine unless the index is the wrong one for the predicate                  |
| Index Only Scan               | All needed columns are in the index           | Best case for read-heavy queries                                          |
| Bitmap Index Scan + Heap Scan | Many-row match, combined via bitmap           | Good when selectivity is moderate, many scattered rows                    |
| Nested Loop                   | For each outer row, probe inner               | High inner `actual rows` → missing index or N+1 shape                     |
| Hash Join                     | Build hash on smaller side, probe with larger | Memory-hungry; watch `work_mem` spills                                    |
| Merge Join                    | Needs sorted input on both sides              | Usually good; expensive if a Sort node is injected                        |
| Sort                          | Explicit ordering                             | Sorts spilling to disk (`external merge`) → raise `work_mem` or add index |
| Parallel Seq Scan             | Seq scan across workers                       | PG9.6+; fine when CPU-bound, bad when disk-bound                          |

### Numbers to read first

- actual time: how long the node took, per loop × loops. Multiply when
  there are many loops.
- rows vs actual rows: estimator accuracy. A 100× mismatch means stale
  statistics, correlated columns, or a predicate the planner cannot estimate.
  Run `ANALYZE`, increase `default_statistics_target` for the column, or add
  `CREATE STATISTICS` for correlated columns.
- Buffers: shared hit vs read: `hit` is cache, `read` is disk. A repeated
  query with high `read` is a cache miss pattern; a single hot query with high
  `read` is a missing index.
- Plan rows under `Rows Removed by Filter`: the query executor is reading
  rows then throwing them away. Push the filter into the index instead
  (composite or partial index).

### `pg_stat_statements`: find the queries to EXPLAIN

```sql
SELECT query, calls, total_exec_time, mean_exec_time, rows
FROM pg_stat_statements
ORDER BY total_exec_time DESC
LIMIT 20;
```

Order by `total_exec_time` first (cumulative impact), then `mean_exec_time`
(per-call pain). Ignore one-offs; focus on high-call and high-time queries.

### Unused indexes

```sql
SELECT s.schemaname, s.relname, s.indexrelname, pg_size_pretty(pg_relation_size(s.indexrelid)) AS size
FROM pg_stat_user_indexes s
JOIN pg_index i ON i.indexrelid = s.indexrelid
WHERE s.idx_scan = 0
  AND NOT i.indisunique
ORDER BY pg_relation_size(s.indexrelid) DESC;
```

Zero-scan indexes cost write throughput. If stats are fresh (no recent
`pg_stat_reset`) and the index has never been used, consider dropping.

## Transaction isolation: what you actually get

### ANSI standard (theoretical)

| Level            | Dirty read | Non-repeatable read | Phantom read | Serial anomaly |
| ---------------- | ---------- | ------------------- | ------------ | -------------- |
| Read Uncommitted | possible   | possible            | possible     | possible       |
| Read Committed   | no         | possible            | possible     | possible       |
| Repeatable Read  | no         | no                  | possible     | possible       |
| Serialisable     | no         | no                  | no           | no             |

### Postgres (what you actually get)

- Read Uncommitted → implemented as Read Committed. No dirty reads, ever.
- Read Committed (default): each statement sees a snapshot at _statement_
  start. Writes block writes on the same row.
- Repeatable Read: snapshot at _transaction_ start. Equivalent to
  Snapshot Isolation; stronger than ANSI RR (no phantoms). Still allows
  write skew (two transactions read overlapping rows and write
  non-overlapping rows, each violating an invariant the other didn't see).
  Updating or locking a row that a concurrent transaction changed and
  committed aborts with `SQLSTATE 40001`. **Callers MUST retry** here too.
- Serialisable: Snapshot Isolation + SSI (Serialisable Snapshot Isolation).
  True serializability. Transactions may abort with
  `SQLSTATE 40001 serialization_failure`. **Callers MUST retry.**

### SQLite (what you actually get)

- SQLite is an excellent embedded/local database, but it has a single-writer
  concurrency model. Treat write contention as a design constraint, not an
  afterthought.
- Prefer WAL mode for apps with concurrent readers and a writer:
  `PRAGMA journal_mode = WAL;`.
- Use `PRAGMA busy_timeout = ...;` or equivalent driver configuration so brief
  writer contention waits instead of failing immediately.
- `BEGIN DEFERRED` is the default; use `BEGIN IMMEDIATE` when the operation is
  definitely going to write and should acquire the write lock up front.
- For server apps with multiple independent writers, background jobs, reporting,
  or operational scaling needs, move to Postgres rather than fighting SQLite's
  concurrency model.

### Write skew, concretely

Classic example: "there must always be at least one doctor on call."

```sql
-- Transaction A
SELECT count(*) FROM doctors WHERE on_call = true;  -- returns 2
UPDATE doctors SET on_call = false WHERE id = 1;

-- Transaction B (concurrent)
SELECT count(*) FROM doctors WHERE on_call = true;  -- returns 2
UPDATE doctors SET on_call = false WHERE id = 2;

-- Both commit; no doctor on call.
```

Under Repeatable Read both commit. Under Serialisable one aborts with
`40001`. The app must retry.

### Rule of thumb

- OLTP default: Read Committed.
- Need consistency across many rows read in one transaction: Repeatable Read
  + retry loop (check for write skew).
- Need invariants enforced across transactions: Serialisable + retry loop.
- Want specific locks: `SELECT ... FOR UPDATE` / `SELECT ... FOR SHARE`,
  regardless of level.
- SQLite default: keep writes short, enable WAL for concurrent readers, and use
  `BEGIN IMMEDIATE` when write-lock acquisition must be explicit.
