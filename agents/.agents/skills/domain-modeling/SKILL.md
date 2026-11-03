---
name: domain-modeling
description: Adding or changing data shapes, records, or statuses, or parsing and normalizing input. Load before editing.
---

# Domain Modeling

## Iron Law

`ILLEGAL STATES MUST BE UNREPRESENTABLE IN THE DOMAIN CORE.`

If the type or data shape permits a state the domain forbids, a future caller
will construct it. Make the state impossible to express rather than guarding
against it.

## When to Use

- Data shape affects correctness: domain data, fields, states, allowed
  combinations, transitions, validation boundaries, value objects, functional
  cores, or effect isolation.
- Reviewing code where I/O, mutation, and business rules are coupled.

## When NOT to Use

- Public HTTP contract details; use `api`. Physical schema; use `database`.
- Module organization, layering, DDD tactical patterns; use `architecture`.
- Broad refactoring sequence; use `refactoring`.

## Rules

1. Decide data shapes and invariants before writing transformations.
2. Distinguish identity, state, value, and time. Prefer immutable records,
   sums, and maps. A class that wraps pure functions is a module; avoid
   classes that bundle behavior with mutable state.
3. Split code into data, calculations, and actions. Maximize data and
   calculations; minimize actions.
4. Parse external input once, at the boundary, into a trusted internal shape.
   Internal code never handles raw strings or maps. Use the ecosystem's
   de-facto schema library (Pydantic in Python, Zod in TypeScript), honoring
   any existing project choice; hand-roll with the same discipline only where
   no clear leader exists. A pure passthrough proxy with no domain logic may
   forward the payload unparsed.
5. Model allowed states as explicit variants, not flag or nullable
   combinations. Split a nullable that means both "missing" and "not loaded"
   into named states. A single independent toggle with no illegal
   combinations can stay a boolean.
6. Names carry the model. A method states its role in the domain process:
   `settleInvoice` or `expireHold`, not `process`, `handle`, or `execute`. A
   suffix like `Service` or `Manager` is fine only with a domain word saying
   what kind. Keep a generic name only where a framework or interop boundary
   requires it.
7. Get approval before implementing a core model, shared invariant, state
   machine, or glossary term future work will bind to; `contract-first` owns
   the approval scope. Disposable or local shapes are not gated.
8. Load `references/dates.md` whenever the diff stores, compares, formats,
   serializes, or computes on dates or times, and `references/money.md`
   whenever it does so on monetary amounts.
9. Name domain concepts with the project glossary's terms, else the issue's
   or spec's words. Use one term per concept in each bounded context. Record
   approved terms in the glossary, asking to start one if none exists.

## Handoffs

- `specify`: contracts whose data shape is being modeled.
- `contract-first`: approval of domain shapes future work depends on.
- `architecture`: module boundaries, locality, layering.
- `database`: schema enforcement for invariants that race under concurrency.
- `proof`: checks at the parse step, where raw input becomes the typed
  domain shape.
- `error-handling`: parse failures, Result/Either shape, error context.
- `async-systems`: mutable places or ownership crossing task boundaries.

## References

- `references/dates.md`: load when time appears in the diff. Timezone-aware
  instants stored in UTC, wall-clock values and recurring events with their
  zone, RFC 3339 wire format.
- `references/money.md`: load when money appears in the diff. Never float,
  amount and currency travel together, ISO 4217, per-currency decimals.
