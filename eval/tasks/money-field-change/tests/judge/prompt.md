Evaluate this coding-agent run.

You receive the task instruction and a bundle with the diff against the starting repository, any new files, and the agent's final message. The bundle is the deliverable.

Read the task instruction at `/tests/judge/instruction.md` and the bundle at `/logs/verifier/judge-bundle.md` only if they are not included below. Do not modify any files.

Score each criterion from 0 to 100.

{criteria}

Prefer evidence-backed, maintainable changes that match the problem's scope.
Penalize superficial test edits, missing edge cases, and changes that only satisfy visible tests.
Penalize sophisticated-looking constructs that fail to deliver the invariant they imply.
Do not penalize adding tests, ADRs, migrations, or documentation when warranted by the task.
