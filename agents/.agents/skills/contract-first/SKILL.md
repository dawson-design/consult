---
name: contract-first
description: Before adding or changing a field, shape, signature, CLI flag, event, or schema that clients or other code read.
---

# Contract First

## Iron Law

`CALLER-FACING INTERFACES AND SHARED STRUCTURE MUST BE APPROVED BEFORE IMPLEMENTATION.`

## When to Use

- A task defines or materially changes a caller-facing interface or shared
  structure: exported function, public type, HTTP endpoint, CLI/env/config
  surface, event payload, file format, database schema, migration step,
  package/module boundary, project layout, or the public surface of a
  significant new module.
- Reviewing whether implementation started before contract approval.

## When NOT to Use

- Internal helper changes, local file moves, or private organization with no
  boundary future work will depend on.
- Typos, formatting, comment-only, or docs-only edits.
- The approach or solution direction is still unsettled; settle it in
  `specify` first.

## Rules

1. A contract is any shape concrete enough that another caller, process,
   service, user, migration step, package, or future module will depend on
   it. An export with no caller outside the change is not yet a contract.
   Working out the actual signatures, types, and shapes is this skill's job.
2. The gate scales with reversal cost. Gate a shape when outside callers will
   bind to it and changing it later means breakage or migration. An additive,
   easily reversed change gets its shape stated in the close-out and
   continues; do not stop the work for it.
3. Approval covers the named shape only. Compatibility (renames, removals,
   aliases, shims, deprecation paths) needs its own explicit decision.
4. An approving design or RFC approves the direction, not the concrete shapes.
   The list of proposed surfaces with evidence is the approval.
5. Silence is not approval. Wait for an explicit approve, revise, or reject.
   When no human can answer in this run (headless, scheduled, or delegated
   sessions), do not deadlock: build the most conservative version, mark the
   contract provisional, and flag the pending decision in the close-out.
6. If implementation discovers a materially different contract, reopen the
   gate.

## Workflow

1. Stop before implementation lands. Do not write source, migrations, or
   config that commit the boundary until approval is recorded.
2. Name the current shape with file/line evidence, or state "new interface"
   or "new structure" for greenfield work.
3. Propose the new shape concretely enough for callers to bind to, and explain
   the boundary: why it belongs here, what owns each side, the key tradeoff.
4. For public renames or removals, ask which compatibility path applies:
   breaking change, alias/shim, deprecation, or old surface retained.
5. List each proposed surface with its evidence and compatibility impact, and
   get one approve/revise/reject.
6. Implement only the approved shape.

## Tripwires

| Trigger | Do this instead | False alarm |
|---|---|---|
| "The design doc already covers this interface" | List each concrete surface with evidence and get one approve/revise/reject. | The exact signature, schema, or surface was itself listed and approved. |
| "I'll implement it first and show the interface after" | Stop before implementation lands; propose the concrete shape and wait for the decision. | The surface is purely internal with no caller-facing or shared boundary. |
| "No objection means it's approved" | Wait for an explicit approve, revise, or reject. | No human can answer in this run; the shape was built conservatively, marked provisional, and flagged. |
| "The rename is implied by the approved shape" | Compatibility needs its own explicit decision. | The approval already named that compatibility path. |

## Handoffs

- `specify`: unsettled approach or solution direction.
- `api`, `database`, `async-systems`, `security`: domain boundary risks.
- `architecture`: shared package/module/project structure.
- `proof`: prove the approved interface at the handoff where callers cross
  it; an approved contract without seam proof is unproven.
