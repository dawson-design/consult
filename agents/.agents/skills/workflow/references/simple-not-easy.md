# Simple, Not Easy

Source: Rich Hickey, [Simple Made Easy](https://www.infoq.com/presentations/Simple-Made-Easy/).

Use this when a change risks ceremony, helper layers, broad skill loading,
or hidden coupling disguised as safety.

## Rule

Simple work reduces the number of things that must be understood together.
Easy work reduces the next step's immediate friction. Prefer simple; reject
easy when it hides data, effects, ownership, time, trust, or rollout risk.

## Checks

1. Name the thing being tangled: data, effect, time, ownership, transport,
   persistence, UI state, release, compatibility, trust, or proof.
2. Add a boundary only for a real change axis, trust boundary, process,
   persistence/transport edge, effect isolation, or proven duplication.
3. Keep behavior, data shape, invariants, and tests close enough that one
   feature can be changed without touring the repo.
4. For narrow work, broad skill loading and extra abstractions are usually
   complexity. For large work, broader skill use can be simple when each
   skill maps to a real risk in the task.
5. Do not add ceremony to signal seriousness. Add only the smallest surface
   that carries a contract, removes hidden coupling, or proves a claim.
6. A hardening step is not simple unless it has a named threat or failure
   mode and an executable or inspectable proof.

## Examples

| Shortcut thought | Simpler move |
|---|---|
| "Add a service/repository/DTO layer" | First name the boundary: transport, persistence, trust, or independent change cadence. |
| "Use every relevant skill" | Load the skills whose routing table rows match the task, not every skill the task touches. |
| "Make a generic helper" | Extract only after two call sites share the same domain meaning, not just similar syntax. |
| "Support both old and new paths" | Ask whether compatibility is required; otherwise keep one path. |
| "This is safer" | State the failure mode and add the proof, or drop it. |

## Handoffs

- `domain-modeling`: when the tangle is shape, state, invariant, parsing, or
  effect order.
- `architecture`: when the tangle is boundary, ownership, layering, or
  change cadence.
- `refactoring`: when the tangle already exists and must be reduced without
  changing behavior.
- `proof`: when simplicity depends on a claim being true.
