# Long Runs

Use this when work spans many steps or independent units, or before
delegating build work to a subagent.

Keep working until the finish line is met, a Rule 2 gate the approved plan
does not cover needs the user, or the next action is destructive.

## Checks

1. State the finish line in the plan as "Done means ...", including what
   must no longer exist. Before closing, check each item against evidence
   and report unmet items as what needs the user's attention.
2. Use the plan file from Rule 3 (`references/plans.md`) as the checklist.
   Tick each step when its proof passes. Add work found mid-run as new
   steps, not as silent scope. The ticked plan is the progress report, so do
   not stop to report progress or to ask whether to continue.
3. When the host can delegate, delegate a Rule 4 stage only after any Rule 2
   gate it holds clears, one stage per subagent. Give each independent unit
   of a stage its own subagent. Pass it the intent, acceptance criteria,
   constraints, the unit's scope, and the resolved path of the `workflow`
   skill's `references/core.md` to read first, because a subagent may not
   get the SessionStart hook that prints it.
4. Split work by context (independent units, exploration, verification),
   never by problem type such as one security agent and one performance
   agent. Never run work that shares state in parallel subagents, because
   each handoff loses detail.
5. The parent checks each unit's evidence before ticking it. A subagent's
   claim that it finished is not proof.
6. A unit that would change a Rule 2 item still needs sign-off. Delegation
   does not move the gate.
