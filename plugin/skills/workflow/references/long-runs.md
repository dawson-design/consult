# Long Runs

Use this when work spans many steps, a large migration or audit, or units
that can be built and checked independently.

## Rule

Keep working until the finish line is met, a Rule 2 gate (including each
Rule 4 stage gate) needs the user, or the next action is destructive. The
plan file tracks progress, so the run needs no other stop to report it.

## Checks

1. State the finish line in the plan as "Done means ...": the behaviors,
   the checks that must pass, and what must no longer exist.
2. Use the plan file from Rule 3 (`references/plans.md`) as the checklist.
   Tick each step when its proof passes. Add work found mid-run as new
   steps, not as silent scope.
3. When a step grows too large for one focused review, split it into
   smaller steps in the plan and continue.
4. When the host can delegate, delegate a Rule 4 stage only after its gate
   clears, one stage per subagent. When a stage splits into independent units
   (services, modules, packages), give each unit its own subagent. Pass it
   the intent, acceptance criteria, constraints, and the unit's scope, and
   give it the resolved path of the `workflow` skill's `references/core.md`
   to read first, because a subagent may not get the SessionStart hook
   that prints it.
   Split by context (independent units, exploration, verification), never by
   problem type (such as one security agent and one performance agent), and
   never run work that shares state in parallel subagents, because each
   handoff loses detail.
5. The parent checks each unit's evidence before ticking it. A subagent's
   claim that it finished is not proof.
6. A unit that would change a Rule 2 item still needs sign-off. Delegation
   does not move the gate.
7. Send short progress updates while working. Between gates, do not stop to
   ask whether to continue.
8. Before closing, check every "Done means" item against evidence. Report
   unmet items as what needs the user's attention.

## Handoffs

- `proof`: the evidence each step or unit must produce.
- `code-review`: the fresh-context review of the combined diff.
- `contract-first` and `domain-modeling`: shapes a unit cannot change alone.
