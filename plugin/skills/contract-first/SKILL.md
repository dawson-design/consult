---
name: contract-first
description: Before adding or changing a field, signature, schema, CLI flag, event, or module boundary that callers rely on.
---

# Contract First

## Iron Law

`GET APPROVAL FOR A CONTRACT BEFORE WRITING CODE THAT DEPENDS ON IT.`

## When to Use

- A task adds or changes a contract: an exported function, public type, HTTP
  endpoint, CLI flag, environment variable, config key, event payload, file
  format, database schema, migration, module boundary, or project layout.
- Checking whether code was written before its contract was approved.

## When NOT to Use

- Internal helper changes, local file moves, or private organization with no
  boundary future work will depend on.
- Typos, formatting, comment-only, or docs-only edits.
- The approach or solution direction is still unsettled; settle it in
  `specify` first.

## Rules

1. A contract is any API, interface, schema, format, or module boundary that
   code, people, or processes outside the change will depend on. An export
   with no outside caller is not a contract yet. This skill writes out the
   exact signatures, types, and fields.
2. Wait for approval when changing the contract later would break callers or
   need a migration. If the change is additive and easy to undo, keep working
   and describe the contract in the close-out.
3. Approval covers the contract or data shape that was shown, nothing more.
   For a rename or removal, get a separate decision on what happens to
   existing callers.
4. An approving design or RFC approves the direction, not the concrete shapes.
5. Silence is not approval. Wait for the person to approve, revise, or reject.
   If nobody can answer in this run, stop and report what needs approval.
6. If you find while building that the approved contract must change, stop
   and get approval for the new version.

## Workflow

1. Do not write code, migrations, or config that depend on the contract until
   it is approved.
2. For each contract, explain why it belongs here, which code owns each side,
   and the main tradeoff.
3. For a rename or removal, ask whether to break existing callers, add an
   alias or shim, deprecate the old version, or keep it.
4. For each contract, show where it is now (file and line, or new), the
   proposed version, and what changes for callers. Then ask once: approve,
   revise, or reject.
5. Build the contract exactly as approved.

## Tripwires

| Trigger | Do this instead | False alarm |
|---|---|---|
| "The design doc already covers this interface" | Follow Workflow step 4 for each contract. | The design listed this exact contract, and the person approved it. |
| "I'll implement it first and show the interface after" | Show the contract first and wait for approval. | Nothing outside the change uses it yet (Rule 1), or the change is additive and easy to undo (Rule 2). |
| "No objection means it's approved" | Wait for the person to approve, revise, or reject. | The person approved this contract in words. |
| "The rename is implied by the approved contract" | Ask what happens to existing callers (Workflow step 3). | The approval already said what happens to existing callers. |

## Handoffs

- `specify`: unsettled approach or solution direction.
- `api`, `database`, `async-systems`, `security`: domain boundary risks.
- `architecture`: shared package/module/project structure.
- `proof`: prove the approved interface at the handoff where callers cross
  it; an approved contract without seam proof is unproven.
