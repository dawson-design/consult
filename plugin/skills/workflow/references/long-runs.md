# Long Runs

Use this when work spans many steps, a large migration or audit, or units
that can be built and checked independently.

## Rule

Keep working until the finish line is met, a Rule 7 gate needs the user, or
the next action is destructive. The plan file tracks progress, so no
intermediate stop is needed to report it.

## Checks

1. State the finish line in the plan as "Done means ...": the behaviors,
   the checks that must pass, and what must no longer exist.
2. Use the plan file from Rule 9 as the checklist. Tick each step when its
   proof passes. Add work found mid-run as new steps, not as silent scope.
3. When a step grows too large for one focused review, split it into
   smaller steps in the plan and continue.
4. When the host can delegate and the work splits into independent units
   (services, modules, packages), give each unit its own subagent. Pass it
   the intent, acceptance criteria, constraints, and the unit's scope.
5. The parent checks each unit's evidence before ticking it. A subagent's
   claim that it finished is not proof.
6. A unit that would change a Rule 7 shape still needs sign-off. Delegation
   does not move the gate.
7. Send short progress updates while working. Do not stop to ask whether to
   continue.
8. Before closing, check every "Done means" item against evidence. Report
   unmet items as what needs the user's attention.

## Handoffs

- `proof`: the evidence each step or unit must produce.
- `code-review`: the fresh-context review of the combined diff.
- `contract-first` and `domain-modeling`: shapes a unit cannot change alone.
