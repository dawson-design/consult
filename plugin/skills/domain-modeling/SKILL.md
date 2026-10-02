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
   no clear leader exists.
5. Model allowed states as explicit variants, not flag or nullable
   combinations. Split a nullable that means both "missing" and "not loaded"
   into named states.
6. Effects (async, exceptions, I/O, clocks, randomness, logging, persistence,
   mutation, shared state) are contagious. Keep them at the imperative shell
   so the functional core stays pure. Core tests run without mocks,
   monkey-patches, databases, network, or global time.
7. Discover abstractions from repeated domain meaning. No generic wrappers,
   base classes, or helper layers before the data proves they pay.
8. Names carry the model. A method states its role in the domain process:
   `settleInvoice` or `expireHold`, not `process`, `handle`, or `execute`. A
   suffix like `Service` or `Manager` is fine only with a domain word saying
   what kind.
9. Each non-trivial invariant or transition gets a Proof Contract (claim,
   data invariant, boundary, check, evidence) via `proof`.
10. A core model, shared invariant, or state machine future work will bind to
    is listed for approval before implementation; `contract-first` owns the
    approval scope. Disposable or purely local shapes are not gated.
11. Load `references/dates.md` whenever the diff stores, compares, formats,
    serializes, or computes on dates or times, and `references/money.md`
    whenever it does so on monetary amounts.

## Tripwires

| Trigger | Do this instead | False alarm |
|---|---|---|
| "Validate it again wherever it's used" | Parse once at each external boundary; internal code takes the parsed type. | A second boundary genuinely receives external data. |
| "Add another boolean flag" | Model allowed states as explicit variants. | The flag is one independent toggle with no illegal combinations. |
| "Pass the request JSON through to the domain" | Convert to an internal domain shape before domain work. | A pure passthrough proxy with no domain logic. |
| "Call the database from the domain function" | Move the effect to the shell. | The function is the shell. |
| "A generic wrapper will save time later" | Wait for repeated domain meaning to prove the abstraction. | The repetition already shares one meaning and rule set. |
| "Name it `process`, `handle`, or `execute`" | Name the method's role in the domain process. | A framework or interop boundary requires the generic name. |
| "Hand-roll the boundary validator" | Use the ecosystem's schema library, honoring any existing project choice. | No clear ecosystem leader exists. |

## Handoffs

- `specify`: contracts whose data shape is being modeled.
- `contract-first`: approval of durable domain shapes.
- `architecture`: module boundaries, locality, layering.
- `database`: schema enforcement for invariants that race under concurrency.
- `proof`: prove at the parse handoff where raw input becomes the typed
  domain shape.
- `error-handling`: parse failures, Result/Either shape, error context.
- `async-systems`: mutable places or ownership crossing task boundaries.

## References

- `references/dates.md`: load when time appears in the diff. Timezone-aware
  always, UTC storage, ISO 8601 wire format, instant vs wall-clock.
- `references/money.md`: load when money appears in the diff. Never float,
  amount and currency travel together, ISO 4217, per-currency decimals.
