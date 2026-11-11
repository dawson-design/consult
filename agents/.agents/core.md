Consult is installed. Its skills load by topic, and the consult:proof skill
loads for any change that needs proving. This core applies to every code
change.

# Consult core

Complexity is the enemy: keep software simple enough to understand, change,
and prove.

## Rules

1. Keep calculations, I/O, and state changes apart. A function that computes
   a result reads no clock, random source, file, network, or database, and
   changes nothing outside itself. Push I/O and mutation to the edges.
2. Build only what the user asked for. Add no route, command, flag, config
   key, environment variable, or startup requirement the request did not
   name. Propose it instead as an opt-in, never as your recommended option,
   so a reply such as "use your recommendations" doesn't build it. Extract an
   abstraction only when code in more than one place serves the same purpose.
4. Write code a reader can follow in one pass. This covers code you write or
   change; don't reshape untouched code. Functions do one thing in about
   25-30 lines. Keep nesting under three levels with guard clauses or
   extraction. Name a condition that joins checks with and/or: a predicate
   when reused, a local otherwise. Null and bounds checks need no name.
5. Don't assume backward compatibility is or isn't required. When a change
   alters behavior that outside callers or stored data depend on, ask, and
   add no shim until the user answers. A fix that restores intended behavior
   needs no question.
7. Before you commit or push, run the project's linter, type checker, and
   formatter check, and fix what they report in code you changed. If a
   project past the prototype stage lacks one, say so and propose adding it.

## House defaults

Where several approaches are sound, use these. Where the project
chose differently, follow the project.

1. **Paradigm:** functional core, imperative shell. Model with immutable
   records, sum types, and maps, with behavior as functions over them. Don't
   put behavior and mutable state in one class, and don't use inheritance
   unless a framework requires it.
2. **Structure:** organize by domain feature or bounded context, keeping each
   behavior's data, logic, and tests together. Add a horizontal layer only at
   a real boundary: process, deploy, trust, persistence, or transport. Use
   aggregates, repositories, and domain services only to protect a real
   invariant.
4. **Errors:** return Result-style values for expected failures, and raise
   exceptions only for bugs. Catch only to recover, translate, retry, or
   terminate, keeping the cause. Translate errors at each boundary. Fail
   closed on auth, validation, and crypto errors.
5. **Data:** represent states as explicit variants, not combinations of flags
   or nullables. Parse external input once at the boundary into trusted types
   with Zod (TypeScript) or Pydantic (Python).
7. **Contracts:** write the contract (OpenAPI spec, types, or schema) before
   the code that implements it.
8. **Live updates:** polling, SSE, or WebSockets. Adopt Kafka or another
   stream only after naming a need they can't meet, such as replay or
   fan-out.
9. **Remote calls:** declare timeout, retry, and failure behavior together.
   Retry only idempotent transient failures, in one layer, with capped,
   jittered backoff.
10. **Correlation ids:** give every error response a correlation id that
    also appears in the log line for that failure.
12. **Refactors:** keep structural and behavioral changes in separate commits.
    Change public interfaces in parallel: expand, migrate callers, contract.
    No big-bang rewrites.
13. **Git:** work on a `feature/`, `fix/`, or `refactor/` branch. Stage files
    by name. One revertible behavior per commit, subject under 72 characters.
    Don't skip hooks.

## Working with the human

The engineer stays in the loop so they keep understanding the system they
own.

1. A feature has two checkpoints:
   - **Plan.** Before writing code, agree the design direction, the
     contracts callers will depend on, and the core data shapes and
     invariants, in the host's plan mode when it has one. Offer two or three
     concrete options, recommend one, and name its main tradeoff.
   - **Data and contracts.** Show the data shapes and contracts as written,
     with the checks that prove them, and wait for approval before building
     logic on them.

   A change that adds no contract, data shape, or dependency, such as a fix
   that restores intended behavior, skips both.
2. Also stop and ask before a migration or anything that deletes or
   rewrites data, adding a dependency, a destructive git operation, and
   anything that publishes: a push, PR, issue, comment, or release.
3. Approval covers what was shown. A generic "Approved" or "Continue"
   covers only the plan or contract just shown, never an earlier proposal
   for work the request did not name; build that only after an explicit
   yes. If building shows that an approved plan or contract must change,
   stop and show the change. If no one can answer, stop and report what
   needs approval.
4. Otherwise, do the work and prove it without asking.
5. Keep each pull request small enough for one person to review in one
   sitting. When a feature needs more, split it into stacked pull requests,
   each one behavior that builds, passes its checks, and can be reverted on
   its own.
6. When a change touches auth, permissions, secrets, deleted data, or a
   public contract, name those files first in the report so the review
   starts there.
7. End with a report in this order: what needs the user's attention; what
   changed and why it is better; how it works (where data enters, the key
   decision, which file to read first); what proves it; what is unproven.
8. When the project keeps ADRs or a decision log, record each checkpoint
   decision and its reason there.
