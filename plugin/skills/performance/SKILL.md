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

## Tripwires

| Trigger | Do this instead | False alarm |
|---|---|---|
| "This code looks slow" | Measure first and name the target metric. | The user asked only for a hypothesis. |
| "Average latency improved" | Check p95/p99 and adjacent metrics before keeping the change. | Batch-only workload where tail latency is irrelevant. |
| "Micro-benchmark is faster, so the app is faster" | Prove the end-to-end path or scope the claim to local mechanics. | The claim is only about the local primitive. |
| "Add a cache" | Name source of truth, invalidation trigger, stale tolerance, and metrics first. | A bounded per-request memo with no cross-request staleness. |
| "TTL handles invalidation" | Use event or key-based expiration; TTL is the safety net. | Best-effort cache where stale data is explicitly acceptable. |
| "The hot key is rare" | Add stampede protection or prove concurrency cannot pile up. | Single-process local cache with bounded callers. |
| "No need to re-measure" | Re-measure under the same workload. | The change was reverted or not kept. |

## Handoffs

- `database`: query plans, indexes, migration risk.
- `observability`: production validation and continuous profiling.
- `security`: sensitive cache contents.
- `error-handling`: cached data in retry or fallback paths.
