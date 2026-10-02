---
name: specify
description: A new service or feature from a brief, or a design choice with open tradeoffs or an ADR. Load before building.
---

# Specify

## Iron Law

`DESIGN-PARTNER MODE: READ THE SYSTEM, DECIDE THE SHAPE TOGETHER, THEN RECORD WHAT WAS AGREED.`

## When to Use

- Work that touches more than one contract, component, module boundary, state
  transition, or domain invariant.
- Adding or changing a public surface, shared structure, or a structural
  runtime dependency (framework, database, ORM, auth client, SDK, job queue).
- Significant new code with no caller-facing boundary: a substantial module,
  non-trivial logic, or a deliberate change to observable behavior.
- Ambiguous or risky intent, or the user asks for an ADR, RFC, tech spec, or
  design note.

## When NOT to Use

- Typos, docs-only edits, internal helper extraction, private file moves,
  dependency bumps with no public surface change, or narrow bug fixes that
  restore intended behavior.
- The design is settled and the user wants a task plan; use `workflow` or the
  host's planning mode.
- A caller-facing interface is already concrete and only needs approval; use
  `contract-first`.

## Rules

1. Design-partner means the agent proposes concrete options and the human
   approves, revises, or rules them out. Neither "the agent decides alone"
   nor "the human should come up with the design" is this mode.
2. Stay above implementation sequencing. Specify owns contracts, states,
   tradeoffs, risks, and decisions. File-by-file edits, pseudocode, and task
   checklists belong to planning after the direction is agreed.
3. Contracts are any caller-facing boundary: function signature, module
   export, public type, error vocabulary, CLI flag, environment variable,
   schema or migration step, event payload, file format, config key. "API"
   does not mean only HTTP.
4. A design written before reading code is speculation. Cite the current
   surface with `file:line` evidence, or name the adjacent convention for
   greenfield work.
5. Ask the smallest question that changes the shape: one recommended option
   with its key tradeoff and approve/revise/rule-out, secondary uncertainties
   as notes. Open questions that block the design are asked now, not left for
   code review.
6. When a design artifact lists interfaces or domain shapes, mark each one
   approved or proposed.
7. Spikes are disposable: ask first, keep them local and small, discard or
   rewrite after convergence.
8. Capture only what will be used, in the smallest useful form, in
   checked-in `docs/` when the team should keep it. Record what the user
   approved, not what was proposed.

## Workflow

1. Frame the design task: intended outcome and the decision that needs
   collaboration. Say that coding waits until the shape is agreed.
2. Read before proposing (Rule 4).
3. Propose one target shape and ask the next design question (Rule 5).
4. Route specialist risks: `domain-modeling` for data, state, effects, and
   invariants; `contract-first` for contract approval; the domain skill for
   the rest.
5. Iterate until the human agrees on the direction or rules it out, then hand
   off to planning, implementation, proof, or review.

## Tripwires

| Trigger | Do this instead | False alarm |
|---|---|---|
| "I already know what the design should be" | Read and cite the current surface first. | Greenfield work with the adjacent convention named. |
| "I'll build it to discover the shape" | Ask first; keep spikes local, small, and disposable. | The user approved a disposable spike. |
| "The design file exists, so the contract is approved" | Get the explicit decision on each concrete surface. | The user explicitly approved those surfaces in the artifact. |
| "Ask about everything at once" | One recommended decision with notes. | None. |
| "The human should come up with the design" | Propose concrete options; the human approves, revises, or rules out. | None. |
| "Run the design gate alongside the host's plan mode" | Converge inside the host's planning surface. | The host has no plan or approval mode. |

## Handoffs

- `contract-first`: contract approval.
- `domain-modeling`: data shapes, invariants, transitions, effects.
- `architecture`: boundaries, ownership, layering, system shape.
- `proof`: the design's proof obligations.
- `documentation`: docs placement once the artifact exists.
- Domain skills as specialist lenses when the design touches them.
