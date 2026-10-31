# Plans

Use this when `workflow` Rule 3 says to save an approved plan, or when
building from a saved plan.

## Rule

Save the approved plan as Markdown: the host's plan file when the host
writes one, otherwise `docs/plans/<slug>.md`. Include intent, acceptance
criteria, constraints, approved Rule 2 items, steps in Rule 4 stage
order, and proof obligations, so a fresh session can build it without the planning
conversation. Record later stages' Rule 2 items as proposed, and mark each
approved when its gate clears.

## Handoffs

- `references/long-runs.md`: the plan as the checklist for a long run.
- `issue-tracking`: filing the plan as tracker work.
