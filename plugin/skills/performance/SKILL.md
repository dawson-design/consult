---
name: performance
description: "Code is slow, times out, or must get faster: latency, throughput, memory, caching. Load before editing."
---

# Performance

## Iron Law

`MEASURE BEFORE OPTIMIZING. MEASURE AGAIN BEFORE KEEPING THE CHANGE.`

## When to Use

- Diagnosing slowness, optimizing latency, throughput, or allocation,
  reading profiles, designing benchmarks, or deciding whether a performance
  change is worth keeping.
- Adding, reviewing, or debugging caches at any layer, including stale data,
  stampedes, and hot keys.

## When NOT to Use

- Concurrency correctness without measured slowness; use `async-systems`.
- Query safety without profiling context; use `database`.
- HTTP cache semantics unrelated to storage or speed; use `api`.

## Rules

1. Name the target metric (p99 latency, throughput, CPU, allocation rate,
   memory, error-budget impact) and its user relevance before changing code.
   Capture a baseline on production-shaped data and concurrency.
2. Optimize the measured bottleneck, not the code that looks suspicious.
3. One performance change per commit, re-measured under the same workload
   and environment, with raw results or profile artifacts saved. Check that
   memory, error rate, tail latency, and CPU did not regress enough to erase
   the win.
4. Latency load generators avoid coordinated omission, or the p99 is
   fiction.
5. Added complexity is kept only when the measured gain justifies it.
6. A cache is kept only after naming its source of truth, invalidation
   trigger, stale tolerance, key contract, stampede protection, TTL/jitter,
   and metrics (hit rate, miss latency, eviction, memory, refresh errors).
   TTL is a safety net, not the invalidation strategy.
7. Cache keys encode every input that changes the value: freshness, tenant,
   permissions, locale, version. Cache contents holding secrets, PII, tenant
   data, or authorization context are sensitive storage; hand off to
   `security`.
8. Cache tests cover stale data and invalidation, not only the warm-cache
   happy path.

## Handoffs

- `database`: query plans, indexes, migration risk.
- `observability`: production validation and continuous profiling.
- `security`: sensitive cache contents.
- `error-handling`: cached data in retry or fallback paths.
