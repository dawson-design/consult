# SQL review reference

Use when reviewing SQL queries embedded in application code, or new
ad-hoc query scripts, in the diff. Apply this alongside the main
`code-review` skill workflow.

## When to defer

- Schema, migrations, indexes added via DDL: defer to the
  `database` skill: it owns production data risk, locking, and
  rollout.
- ORM-generated queries: review the call site (N+1, eager
  loading) using the language reference (e.g. `ruby.md` for AR,
  `csharp.md` for EF Core, `python.md` for SQLAlchemy).
- This file focuses on hand-written SQL in app code, raw queries,
  views, and stored procedures.

## High-signal review checks

- Parameterised queries: every value derived from user input
  must use bind parameters, not string concatenation. String-built
  SQL is a Critical security finding regardless of how "trusted" the
  input looks.
- **No `SELECT *` in app code**: explicit column lists keep the wire
  contract stable when the schema grows. `SELECT *` is fine in
  ad-hoc queries and tests.
- Indexes covering predicates: `WHERE` columns, `JOIN` keys, and
  `ORDER BY` columns should be indexed (or the planner should pick a
  reasonable scan). Ask for the `EXPLAIN` plan when the query is on
  a hot path.
- Set-based, not row-by-row: a loop in the application that
  fires one query per row is almost always wrong. Push the work into
  a single `INSERT ... SELECT`, `UPDATE ... FROM`, or `MERGE`.
- Deterministic ordering for pagination: `ORDER BY created_at`
  alone is not stable across rows with the same timestamp. Add a
  tiebreaker (`ORDER BY created_at, id`) or use keyset pagination.
- `OFFSET` for deep pagination: scans + skips. Past the first
  few pages, switch to keyset (cursor) pagination.
- `NULL` semantics: `col = NULL` never matches; use `IS NULL` /
  `IS NOT NULL`. Aggregates ignore `NULL` (`COUNT(col)` ≠
  `COUNT(*)`); be explicit.
- `JOIN` types: an unintended `LEFT JOIN` matched against a
  non-null column in `WHERE` silently becomes an `INNER JOIN`. Spot
  filters on the right side of a left join.
- Transaction scope: keep transactions short. Long transactions
  hold locks and bloat MVCC. `BEGIN ... call_external_api ... COMMIT`
  is a finding: pull the side effect outside.
- Lock escalation / hot rows: `UPDATE` on a heavily-contended
  row, `SELECT FOR UPDATE` without a clear ordering, can deadlock.
  Note any new locking pattern.
- Aggregations: `GROUP BY` columns must include every non-aggregated
  column in the `SELECT`. Some dialects allow it implicitly, but
  the result is undefined.
- Type coercion: implicit casts in predicates can prevent index
  use. `WHERE id = '123'` against an `integer` column may scan.
- Date/time: store and compare in UTC; truncate explicitly
  (`date_trunc(...)`) rather than relying on session timezone.
- Materialised views and triggers: any new trigger or
  materialised view changes invariants on writes: call out the
  impact on existing call sites and refresh strategy.

## Anti-patterns / red flags

- String concatenation building a query (any language).
- `SELECT *` in production code paths.
- `OFFSET 100000` in user-facing pagination.
- `WHERE col = NULL` instead of `IS NULL`.
- `LEFT JOIN x ON ... WHERE x.col = 'y'` (filter forces inner join).
- Long-running `BEGIN ... COMMIT` spanning external calls.
- New `DELETE` without a `WHERE` clause review (or a `LIMIT`-style
  guard if the dialect supports it).
- `LIKE '%foo%'` on a hot path with no full-text index.
- `ORDER BY RAND()` / `ORDER BY random()` on a non-trivial table.
- New trigger, view, or stored procedure without a test that
  exercises it.

## Sources

- "Use The Index, Luke!": <https://use-the-index-luke.com/>
- PostgreSQL EXPLAIN docs:
  <https://www.postgresql.org/docs/current/using-explain.html>
- MySQL Optimizer docs:
  <https://dev.mysql.com/doc/refman/8.0/en/optimization.html>
- Joe Celko, *SQL for Smarties*: canonical for set-based thinking.
- OWASP SQL Injection Prevention Cheat Sheet:
  <https://cheatsheetseries.owasp.org/cheatsheets/SQL_Injection_Prevention_Cheat_Sheet.html>
