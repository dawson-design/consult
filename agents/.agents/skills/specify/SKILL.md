---
name: specify
description: A new service or feature from a brief, or a design choice with open tradeoffs or an ADR. Load before building.
---

# Specify

## Iron Law

`READ THE CODE, PROPOSE A DESIGN, AND GET AGREEMENT BEFORE BUILDING.`

## When to Use

- Work that touches more than one contract, component, module boundary, state
  transition, or domain invariant.
- Adding or changing a contract, or a runtime dependency that's hard to swap
  later (framework, database, ORM, auth client, SDK, job queue).
- Significant new code with no caller-facing boundary: a substantial module,
  non-trivial logic, or a deliberate change to observable behavior.
- Ambiguous or risky intent, or the user asks for an ADR, RFC, tech spec, or
  design note.

## When NOT to Use

- Typos, docs-only edits, internal helper extraction, private file moves,
  dependency bumps that change no contract, or narrow bug fixes that restore
  intended behavior.
- The design is settled and the user wants a task plan; use `workflow` or the
  host's planning mode. To file it as tracker work, use `issue-tracking`.
- A contract is already written out and only needs approval; use
  `contract-first`.

## Rules

1. Design the decisions, not the build steps: contracts, data shapes,
   states, tradeoffs, and risks. Leave file-by-file edits, pseudocode, and
   task lists for the plan, after the design is agreed.
2. Contracts are what `contract-first` Rule 1 defines, not only HTTP APIs.
3. Read the code before proposing a design. Cite the current code with
   `file:line`, or, when no code exists yet, name the nearby convention it
   follows.
4. Propose concrete options, recommend one, and let the user decide. Don't
   decide alone, and don't ask the user to invent the design. Ask one
   question at a time, and only questions whose answer would change the
   design. Give your recommendation and its main tradeoff, and ask the user
   to approve, revise, or rule it out. Put smaller doubts in notes. Ask
   questions that block the design now, not in code review.
5. In a design doc, mark each contract and data shape approved, proposed, or
   pending. Mark it pending when the `workflow` Rule 9 stages before it are
   not built yet, even if the user agreed to it. It stays pending until that
   stage's sign-off.
6. Ask before writing a spike (throwaway code that answers a design
   question). Keep it local and small, and delete or rewrite it once the
   design is agreed.
7. Write down only what someone will use, and keep it short. Put it in
   checked-in `docs/` when the team should keep it. Record what the user
   approved, not what you proposed.

## Workflow

1. State the outcome and the decision the user needs to make. Say that coding
   waits until the design is agreed.
2. Read before proposing (Rule 3).
3. Propose your recommended design and ask the next question.
4. Load `domain-modeling` for data, states, effects, and invariants,
   `contract-first` for contract approval, and the matching skill for
   anything else.
5. Repeat until the user agrees on the design or rules it out, then move to
   planning, building, proof, or review.

## Tripwires

| Trigger | Do this instead | False alarm |
|---|---|---|
| "I already know what the design should be" | Read and cite the current code first. | No code exists yet, and the nearby convention is named. |
| "I'll build it to find the design" | Ask first; keep spikes local, small, and disposable. | The user approved a disposable spike. |
| "The design file exists, so the contract is approved" | Get the explicit decision on each contract and data shape. | The user explicitly approved them in the doc once their earlier `workflow` Rule 9 stages existed. |
| "Ask about everything at once" | One recommended decision with notes. | None. |
| "The human should come up with the design" | Propose concrete options; the user approves, revises, or rules out. | None. |
| "Run the design discussion alongside the host's plan mode" | Hold it inside the host's plan mode. | The host has no plan or approval mode. |

## Handoffs

- `contract-first`: contract approval.
- `domain-modeling`: data shapes, invariants, transitions, effects.
- `architecture`: boundaries, ownership, layering, system structure.
- `proof`: acceptance criteria for the design.
- `documentation`: docs placement once the design doc exists.
- Other domain skills when the design touches their area.
