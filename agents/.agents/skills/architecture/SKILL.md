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
  and public surfaces.
- Choosing API style or data store family before a specialist skill owns the
  detailed shape.
- Deciding whether DDD tactical patterns earn their keep.
- Reviewing code where one behavior is scattered across many files for no
  technical reason.

## When NOT to Use

- Data shape, invariant, and effect discipline; use `domain-modeling`.
- Public HTTP contract details; use `api`. Physical schema; use `database`.
- Reshaping existing code while preserving behavior; use `refactoring`.
- Local file moves or private helper extraction that create no shared
  boundary: explain the choice and proceed.

## Rules

1. Feature behavior, data shapes, invariants, and tests live close enough to
   change together, and one focused behavior can be run without invoking the
   whole suite.
2. Functions do one thing, stay around 25-30 lines, and keep conditionals and
   loops under three nesting levels. Guard clauses, extraction, or composition
   come before another nested branch.
3. Horizontal layers exist only for a real boundary: process, deploy, trust,
   persistence, transport, or proven duplication. A layer that scatters one
   behavior by default is harmful.
4. A module boundary says what crosses it, what assumptions hold, and what
   callers must not depend on. Callers depend on the contract, never the
   internal shape.
5. Data flow is explicit: where external data enters, where it becomes
   trusted, where domain work happens, what output shape leaves. These are
   roles, not required folders. Raw external payloads do not leak past the
   parse boundary.
6. DDD patterns (aggregates, repositories, factories, domain services) and
   bounded contexts are used only when they protect a real invariant,
   workflow, or a word that means different things in different places.
7. Shared structure is user-owned. Project layout, package/module boundaries,
   public library shape, and cross-component ownership future work will
   depend on route through `contract-first`, which owns the approval scope.
8. Decisions future readers cannot recover from the code (why this boundary,
   why this shape, what was rejected) are recorded in an ADR, comment, or
   commit message.

## Tripwires

| Trigger | Do this instead | False alarm |
|---|---|---|
| "Start with controller/service/repository/DTO layers" | Group by capability first; add a layer only where a real technical boundary justifies it. | The layer maps to a process, deploy, trust, persistence, or transport boundary. |
| "These two features look the same, share the code" | Share code only when the reused value has the same meaning and rules in both contexts. | One domain rule with one authoritative home. |
| "Add a repository/factory/aggregate for structure" | Add DDD patterns only when they protect a named invariant, workflow, or boundary. | The pattern guards a named invariant. |
| "Move the files now, decide the boundary later" | Decide the boundary before using `refactoring` to move files. | The move is private organization that creates no shared boundary. |
| "Create the shared package; asking can wait" | Ask before locking in shared structure future work will depend on. | Private file moves that establish no boundary. |
| "Another layer will make this cleaner" | Add a layer only for an independent change axis, process, deploy, trust, persistence, transport, or proven duplication. | The axis is real and named. |

## Handoffs

- `specify`: compare current and proposed contracts before boundary decisions.
- `contract-first`: approval of shared structure and public surfaces.
- `domain-modeling`: module data shapes, invariants, effects.
- `refactoring`: move existing code toward the chosen structure.
- `api`: public HTTP contract details, including middleware placement.
- `database`: physical schema, migrations, indexes.
- `proof`: handoff tests at each module boundary the architecture defines.
