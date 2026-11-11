# Consult improvement plan

Written 2026-11-11, after a review of v2 (20.0.1).

Consult should shrink to two jobs. The first is steering the agent to the
simpler of two sound designs. The second is keeping a project's structure
from eroding as it grows. Public evals support both jobs and little else.
This plan gets there in five steps:

1. Close the gaps in Consult's own evidence.
2. Measure both jobs with outside metrics.
3. Cut what shows no lift.
4. Trial four choice rules.
5. Move the size limits into each project's linter.

## Status

As of 2026-11-11 the parts that need no agent trial are built and
unit-tested. No trial has run on any of them.

| Step | Built | Waiting on |
|---|---|---|
| 1 | Placebo arm, per-stage line and simplicity tables, default 9 probe fix | The stub and placebo runs, and the citation check |
| 2 | Follow-up change test, six forks tasks | Their first runs, the SlopCodeBench arm, fresh sessions, and a brownfield start |
| 3 | The four core lines and the self-review sentence are cut | The stub result for skills, and the checkpoint trial |
| 4 | Nothing | The SlopCodeBench and forks results |
| 5 | Nothing | The SlopCodeBench result |

## What the review found

- **Steering works.** Four house defaults go from 0.20 or below to 1.00
  against bare Claude Code.
- **Direction is unproven.** The checks score conformance to the house
  style. Consult writes about twice the lines for the same behavior, with
  no reward lift (-0.06) at 2.1 times the tokens.
- **The tangle evidence is thin.** Simplicity holds at 0.88 while bare
  falls from 0.82 to 0.74. Two of the score's five parts restate Consult's
  own rules, and the test is one session, five stages, and about 700
  lines.
- **No v2 run measures the skills.** The seven auto-loading skills hold
  48 rules. Ten have checks, and none has a v2 result.

## What public evals show

These evals test models and agents on software work. The figures come from
search summaries, because this session could not reach arxiv.org or
metr.org. Check each against its source before quoting it on the site.

| Eval | Finding | What it means for Consult |
|---|---|---|
| SWE-bench Verified | Top scores sit near 90%, and the benchmark is widely treated as saturated. | Fixing a stated bug needs no guidance. |
| METR merge study | Maintainers would reject about half of the PRs that pass the tests. Their reasons: verbose or off-convention code, breaking other code, and missed functionality. | The target is a change a maintainer would merge, not a passing test. |
| FrontierCode | Maintainer criteria include limits on files and lines touched. The top model scores 13.4% on the hardest subset. | Scope and size limits are on target. Twice the lines is not. |
| SlopCodeBench | Structure erodes in 77% to 80% of runs. Agent code is 2.2 times as verbose as human code. Quality prompts lower the starting point by up to a third, and the decline stays as steep. | Consult's flat line would be a first for a prompt, so it needs an outside test. |
| SWE-CI | Across long maintenance runs, most models break a passing test in over 75% of tasks. | Rerun the tests that passed before the change. |
| CodeTaste | Agents carry out a specified refactoring well. They do far worse when they must decide what to restructure. Planning first nearly doubles the match with human refactorings. | Guidance belongs on when to reshape, not how. |
| Ambig-SWE, Ask or Assume | Models rarely notice that a task is underspecified. Asking recovers most of the lost performance. | A rule on when to ask has measured value. |
| ImpossibleBench | Models game tests that conflict with the spec. One strict prompt cut a model's rate from 92% to 1%. | A single negative constraint on tests works. |
| SusVibes | About 80% of working solutions are insecure. Security hints gained about 3 points of security and cost up to 7 points of correctness. | The security gap is real, and prose does not close it. |
| ETH AGENTS.md study | Context files raise cost by over 20%. Generated files lower success, and repository overviews do not help. Files help with non-standard practices. | Hold only what the agent cannot infer from the code. |
| SWE-Skills-Bench | 39 of 49 public skills add nothing. Three lower the pass rate with guidance that conflicts with the project's versions. | Generic practice skills cost tokens for no gain. Dated facts need a project-wins clause. |
| Guardrails Beat Guidance | Only negative constraints help. Random rules do about as well as curated ones. | Write rules as constraints, and test against a placebo. |
| GitClear 2026, CodeScene | Duplicated blocks are up 81% and refactoring moves are down 70% since 2022. Agents break more in unhealthy code. Both are vendor data. | Duplication is the measured form of tangle, and structure compounds. |

The table shows three patterns:

1. **Models get a stated task right.** The gap is whether a maintainer
   would accept the change: small, in the project's style, and no worse
   for the code around it.
2. **Prose about good practice does not move outcomes.** One-line
   constraints and mechanical checks do.
3. **Prompts change where a project starts, not how fast it decays.** No
   public result shows guidance alone changing the slope.

## What Consult should hold

**Keep or add.** Each item picks a side or sets a floor that an eval shows
models miss.

- Scope and size: core rule 2.
- Follow the project: the house defaults' opening line.
- Structure choices with one simpler side: defaults 1, 2, 5, and 8.
- When to ask: core rule 5 and the plan checkpoint.
- Tests: proof rule 8 (rerun existing tests, weaken none).
- Two new rules on trial: when to reshape, and one home per rule.

**Leave out.** Models already do these, or prose does not help.

- How to fix, debug, test, or refactor.
- Surface style: core rule 3, default 11, and default 15 show no lift.
- Security prose: core rule 6 shows no lift, and SusVibes explains why.
- The self-review ban: the first sentence of "Working with the human"
  rule 6 scores 1.00 in both arms.
- Overviews and architecture descriptions.
- Dated specifics that do not yield to the project.

**Unproven.** Test these before keeping them.

- Defaults that add code: 7 (a hand-written OpenAPI file), 9 (retries),
  and 10 (correlation ids).
- Default 4 outside TypeScript, and the JSON:API default in `api` rule 4.
- Every skill body.

## Step 1: Close the gaps in Consult's own evidence

These use the existing harness and need no new tasks.

1. **Run the stub arm on `houseStyle`.** It separates the core's effect
   from the skill bodies'.
2. **Add a placebo arm.** Use a core of the same length made of unrelated
   rules. It separates Consult's content from the effect of any rules.
3. **Split the line count.** Report source, test, and spec lines per stage
   for each arm.
4. **Report the five simplicity parts per stage.** The result should show
   which part drives bare's decline.
5. **Fix the default 9 probe.** It scores a retry on a 503 that the brief
   never asked for.
6. **Check a citation.** `AGENTS.md` says SWE-Skills-Bench found no effect
   in 92 of 98 skills. The paper's abstract says 39 of 49.

Done when the lift report shows consult against stub, stub against placebo,
and placebo against bare, each with an interval.

## Step 2: Measure both jobs with outside metrics

1. **Run SlopCodeBench with a Consult arm.** The Harbor hub lists a
   36-task conversion, and Consult's eval already runs on Harbor.
   Compare bare, the benchmark's own quality prompt, and Consult on the
   slope of verbosity and erosion. Start with a subset of problems.
2. **Add a follow-up change test.** A bare agent in a fresh session makes
   a held-out sixth change to each arm's final tree. Score pass rate,
   tokens, files touched, and lines changed.
3. **Build a forks suite.** Each task has two sound designs, and the
   hidden check accepts both. Score which one the agent chose and its
   source lines. SWE-Lancer's manager tasks set the precedent.

   | Fork | Simpler side |
   |---|---|
   | Cache or recompute | Recompute |
   | Queue or inline call | Inline call |
   | Retry or timeout only | Timeout only |
   | Config key or constant | Constant |
   | Special case or reshape | Reshape |
   | Parallel copy or the rule's existing home | Existing home |

4. **Test the real conditions for tangle.** Give stages 3 to 5 fresh
   sessions, and add a brownfield start. `proof-organize-tangled-seam` is
   a seed.

Decision: other prompts move only the starting point on SlopCodeBench. If
Consult does the same, the second job rests on step 5 and not on prose.

## Step 3: Cut what shows no lift

1. **Cut four core lines and one sentence now.** Together they free 97 of
   the core's 994 words.
   - Core rules 3 and 6, and defaults 11 and 15.
   - The first sentence of "Working with the human" rule 6, the
     self-review ban. It guards a v1 habit that v2 no longer prompts, and
     the `code-review` description still sends the user to a fresh
     session. The second sentence stays and opens "When a change touches
     auth", so the report still names the risky files first.
2. **Cut skills by the stub result.** A skill body that adds no lift
   becomes user-invoked, or shrinks to its floors. `proof` goes first. It
   holds 875 words, loads on most changes, and has checks for two of its
   nine rules.
3. **Trial a conditional second checkpoint.** "Working with the human"
   holds 358 of the core's words, and Consult costs 2.1 times the tokens.
   Stop for approval of data and contracts only when the plan left one
   open. Compare cost and reward with the current rule.

Done when every always-on line has a measured lift or an outside result
behind it.

## Step 4: Trial four choice rules

Each rule is a constraint with one way out. The words come from step 3's
cuts.

| Rule | Draft wording | Evidence |
|---|---|---|
| Moving parts, replacing default 8 | Don't add a cache, queue, retry layer, background job, second store, or service until you can name the need the simpler design can't meet. | FrontierCode, SlopCodeBench |
| Remote calls, replacing default 9 | Set a timeout on every remote call. Don't retry unless the request asks for it; then retry only idempotent transient failures, in one layer, with capped, jittered backoff. | Review finding |
| One home | Don't write a business rule a second time. Extend it where it lives, and delete the path a change replaces. | GitClear |
| Reshape first | Don't add a special case to a shape that no longer fits. Reshape it first in its own commit, unless the user asked for the smallest patch. | CodeTaste |

CodeTaste shows the hard part is deciding what to reshape. The fourth rule
needs a concrete cue, such as a second flag on one record.

A rule stays when its fork shows the simpler side chosen more often than
bare, with an interval that excludes zero. It must also leave
`follow-the-project` unchanged. Follow "Changing a rule" in `AGENTS.md`
for each edit.

## Step 5: Put the limits in the linter

1. **Have `scaffolding` write the limits into lint config:** function
   size, nesting depth, complexity, and import cycles. Core rule 7 already
   runs the linter, so the limits outlive the session and the plugin.
2. **Score erosion, not the lint pass.** An agent can meet a limit with a
   cosmetic split.
3. **Add no architecture overview file.** The ETH study found they raise
   cost without helping.

Done when a bare agent, on a repository Consult scaffolded, holds the
erosion slope without Consult installed.

## Order

Step 1 comes first because it is cheap and decides step 3. Step 2's
SlopCodeBench run comes before any new rule, because it decides how much
weight prose can carry. Step 3 frees the words that step 4 spends. Step 5
follows the SlopCodeBench result.

## Open questions

1. Keeping the engineer's understanding is a third job. Does it justify
   2.1 times the cost alone, or do the checkpoints and report have to pay
   for themselves in outcomes?
2. Every result so far is Opus 5.5 at extra-high effort on TypeScript.
   Which second model and language come next?

## Sources

- [SlopCodeBench](https://arxiv.org/abs/2603.24755), its
  [repository](https://github.com/SprocketLab/slop-code-bench), and the
  [Harbor conversion](https://hub.harborframework.com/datasets/gabeorlanski/slopcodebench)
- [METR: Many SWE-bench-Passing PRs Would Not Be Merged into Main](https://metr.org/notes/2026-03-10-many-swe-bench-passing-prs-would-not-be-merged-into-main/)
- [Cognition: Introducing FrontierCode](https://cognition.ai/blog/frontier-code)
- [SWE-CI](https://arxiv.org/abs/2603.03823)
- [CodeTaste](https://arxiv.org/abs/2603.04177)
- [Ambig-SWE](https://arxiv.org/abs/2502.13069) and
  [Ask or Assume?](https://arxiv.org/abs/2603.26233)
- [ImpossibleBench](https://arxiv.org/abs/2510.20270)
- [SusVibes: Is Vibe Coding Safe?](https://arxiv.org/abs/2512.03262)
- [Evaluating AGENTS.md](https://arxiv.org/abs/2602.11988)
- [SWE-Skills-Bench](https://arxiv.org/abs/2603.15401) and
  [SkillsBench](https://arxiv.org/abs/2602.12670)
- [Guardrails Beat Guidance](https://arxiv.org/abs/2604.11088)
- [GitClear: The Maintainability Gap](https://gitclear.com/the_ai_code_quality_maintainability_gap)
- [CodeScene: Code for Machines, Not Just Humans](https://tools.prnewswire.com/en-us/live/20823/release/20260128EN71904)
- [SWE-Lancer](https://openai.com/index/swe-lancer/)
- [SWE-bench Pro leaderboard notes](https://www.morphllm.com/swe-bench-pro)
- [Thoughtworks Radar: Habit Hooks](https://www.thoughtworks.com/radar/tools/habit-hooks)
