---
name: async-systems
description: Queues, workers, batch jobs, concurrency limits, retries, streams, or message payloads. Load before editing.
---

# Async Systems

## Iron Law

`EVERY ASYNC BOUNDARY NAMES ITS CONTRACT, OWNER, LIFETIME, BACKPRESSURE, AND FAILURE SEMANTICS.`

## When to Use

- Designing or reviewing async execution, cross-process message contracts,
  background work, live updates, streams, brokers, ordering, and backpressure.
- Investigating races, deadlocks, stuck tasks, starvation, retry exhaustion,
  dead jobs, lag, poison messages, or delivery issues.

## When NOT to Use

- Request/response API design; use `api`.
- Remote-call timeout and retry policy; use `error-handling`.
- Metrics, alerts, runbooks; use `observability`.
- Transaction isolation; use `database`.

## Rules

1. For user-facing live updates, start with polling, SSE, or WebSockets.
   Escalate to Kafka, Kinesis, or Redis Streams only after naming the
   requirement the simpler transport cannot meet: independent replay, long
   retention, audit history, offline catch-up, multi-service fanout,
   consumer-group scaling, partitioned throughput, or durable recovery.
   Record that requirement with the choice.
2. Immutable data crosses async boundaries; mutable state has one owning
   scope. Job payloads carry stable identifiers and immutable inputs, never
   live session, request, or thread-local state.
3. Every spawned task belongs to a scope that cancels, awaits, or supervises
   it, with a deterministic shutdown path.
4. Every queue, channel, pool, stream, and buffer has a bound and an overflow
   policy. Blocking work cannot starve latency-sensitive work.
5. Locks are an escape hatch: short, globally ordered, and never held across
   I/O, awaits, or user callbacks.
6. Retried jobs and stream consumers are idempotent, deduplicated, or marked
   non-retryable with a reason. Retry policy itself belongs to
   `error-handling`.
7. Cross-process jobs, events, and stream records are versioned contracts,
   with the schema kept in a versioned source of truth. Route contracts that
   independently deployed participants or retained messages bind to through
   `contract-first`.
8. Every running consumer version can read every message version that a
   running producer emits or that is still queued, retained, or replayable. A
   registry's compatibility mode must enforce this. Delivery guarantee, ordering key, retention, replay,
   ack/offset, DLQ, and poison-message handling are explicit for streams.
9. Silent async failure is a bug. Exhausted jobs, lag, dropped events, and
   dead work have visible signals and tests.

## Tripwires

| Trigger | Do this instead | False alarm |
|---|---|---|
| "Pass the session/request object to the job" | Pass stable IDs and immutable parameters; reload live state inside the job. | The payload already is stable IDs and immutable data. |
| "Rescue the job failure and log it" | Re-raise, mark terminal, or record the failure so exhausted work is visible. | Best-effort work with an explicit drop policy. |
| "Enqueue inside the transaction" | Enqueue after commit or use a transactional outbox when the job reads transaction-written state. | The job reads none of the transaction's writes. |
| "One queue is enough for everything" | Isolate user-facing work from bulk queues with priority, concurrency, timeout, or separate workers. | The workload is uniform with no user-facing latency expectation. |
| "We need Kafka for this" | Name the requirement polling, SSE, or WebSockets cannot meet before choosing a broker. | The requirement is named and recorded. |
| "It's just JSON on a topic" | Define a versioned message schema and check consumer compatibility, using the existing registry when present. | The channel is in-process, with no retained messages or independent consumer. |

## Handoffs

- `contract-first`: approval for the message contracts Rule 7 routes there.
- `domain-modeling`: remove shared mutable state from the core.
- `api`: public subscription, webhook, or SSE surface.
- `error-handling`: retry budgets and dependency-failure policy.
- `database`: transactional enqueue, outbox/CDC, locking.
- `observability`: queue depth, lag, dead-job dashboards and alerts.
- `release`: worker draining and deploy compatibility.
- `debugging`: existing races, deadlocks, stuck jobs.
- `official-source-check`: registry and schema-format compatibility behavior.
- `proof`: validate serialized producer output and show affected consumers
  handle every message version Rule 8 covers; assert ownership, ordering,
  backpressure, and failure at the async boundary.

## References

- `references/browser-streaming.md`: load when choosing between polling, SSE,
  and WebSockets for live updates.
