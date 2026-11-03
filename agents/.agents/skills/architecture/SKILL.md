---
name: architecture
description: "Deciding where code or logic should live: module boundaries, layering, coupling."
---

# Architecture

## Iron Law

`ORGANIZE BY WHAT CHANGES TOGETHER. BOUNDARIES EXPOSE CONTRACTS, NOT INTERNAL STEPS.`

## When to Use

- Choosing between feature-oriented organization and horizontal
  controller/service/repository/DTO layers.
- Choosing shared project, package, or module boundaries, bounded contexts,
  and public contracts.
- Choosing API style or data store family before a specialist skill designs
  the details.
- Deciding whether DDD tactical patterns are worth their cost.
- Choosing a transport for live updates or event streams.
- Reviewing code where one behavior is scattered across many files for no
  technical reason.

## When NOT to Use

- Data shapes, invariants, and effects; use `domain-modeling`.
- Public HTTP contract details; use `api`. Physical schema; use `database`.
- Restructuring existing code while preserving behavior; use `refactoring`.
- Local file moves or private helper extraction that create no shared
  boundary: explain the choice and proceed.

## Rules

1. Feature behavior, data shapes, invariants, and tests live close enough to
   change together, and you can run the tests for one behavior without
   running the whole suite.
2. Horizontal layers exist only for a real boundary: process, deploy, trust,
   persistence, transport, or proven duplication. A layer that scatters one
   behavior by default is harmful. Share code across features only when the
   shared value has the same meaning and rules in each.
3. A module boundary says what crosses it, what assumptions hold, and what
   callers must not depend on. Callers depend on the contract, never the
   internals. Decide a shared boundary before moving files toward it.
4. Data flow is explicit: where external data enters, where it becomes
   trusted, where domain work happens, what output leaves. These are
   roles, not required folders. Raw external payloads do not leak past the
   parse boundary.
5. DDD patterns (aggregates, repositories, factories, domain services) and
   bounded contexts are used only when they protect a real invariant,
   workflow, or a word that means different things in different places.
6. For user-facing live updates, start with polling, SSE, or WebSockets.
   Adopt Kafka, Kinesis, or Redis Streams only after naming the requirement
   the simpler transport cannot meet, such as independent replay, long
   retention, offline catch-up, or multi-service fanout, and record it with
   the choice.

## Handoffs

- `specify`: compare current and proposed contracts before boundary decisions.
- `contract-first`: approval of contracts, including module boundaries and
  project layout.
- `domain-modeling`: module data shapes, invariants, effects.
- `refactoring`: move existing code toward the chosen structure.
- `api`: public HTTP contract details, including middleware placement.
- `database`: physical schema, migrations, indexes.
- `proof`: handoff tests at each module boundary the architecture defines.
