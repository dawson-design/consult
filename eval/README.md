# Consult Evals

This suite measures whether a coding agent does better work on the same task
with Consult skills installed than without them. It runs on
[Harbor](https://docs.harborframework.com). Harbor sandboxes each trial in
Docker, injects the skills into the agent's native skills directory, and
records an ATIF trajectory.
[RewardKit](https://docs.harborframework.com/core-concepts/rewardkit/quick-start)
scores the result.

The number to read is **lift**: the Consult arm's reward minus the bare arm's
reward, per task and per suite. The bare arm is the same agent, model, and
settings with no skills and, for Claude Code, without the plugin hook. Absolute rewards drift with model versions; lift is
the comparison that holds.

Measured hosts: `claude-code` and `codex`. Harbor also has skill-aware
integrations for Cursor, Gemini CLI, Copilot, OpenCode, and Pi. Adding one of
them is an agent fragment under `agents/`, not a harness change.

## Setup

```sh
uv tool install harbor            # 0.23.0 at the time of writing
docker info                       # Docker must be running
cd eval && uv sync                 # pyyaml for the driver scripts
```

Auth uses subscriptions, not API keys:

- Claude Code and the judge: run `claude setup-token` and export the result as
  `CLAUDE_CODE_OAUTH_TOKEN`. The driver sets `CLAUDE_FORCE_OAUTH=true` so the
  agent bills the subscription and aborts the run when the token is missing.
- Codex: a ChatGPT-authenticated `~/.codex/auth.json`. The driver sets
  `CODEX_FORCE_AUTH_JSON=true`, which uploads that file into the sandbox.

Keep those two `FORCE` flags in the host environment rather than in a job
config. Harbor scrubs the value of every credential-named agent env var from
the trial files. A literal `1` there rewrites every `1` in `trajectory.json`.

## Run

```sh
uv run scripts/run.py --suite smoke --agent claude-code --install-only   # wiring and auth only
uv run scripts/run.py --suite smoke --agent codex --arms bare,consult    # cheapest real run
uv run scripts/run.py --suite core --agent claude-code --attempts 3      # both arms, lift table
uv run scripts/run.py --suite rules --agent claude-code --preflight-only # does the agent load Consult?
harbor view runs                                                          # browse trials and rewards
```

Every run that includes the consult arm starts with a skill-loading preflight.
The preflight runs each task's first turn in the consult arm with verification
off. It prints which Consult skills each task loaded. `run.py` stops before
the arms when fewer than `--preflight-min` (default 0.5) of those trials read a
Consult skill. Past that point the consult arm would measure the bare agent.

- `--preflight-attempts`: trials per task.
- `--preflight-only`: stop after the readout.
- `--skip-preflight`: run the arms regardless.
- `--effort`: override the agent fragment's `reasoning_effort` for the
  preflight and every arm. Claude Code runs at `xhigh` by default, the
  maintainer's own setting for Opus 5.5.

`run.py` writes one Harbor job per arm under `runs/`, runs them in order, then
calls `scripts/lift.py <bare-job> <consult-job>`, which prints a per-task table
and writes `runs/lift/<job>.json` and `.md`. Pass `--concurrency` to change
`n_concurrent_trials`. The default of 2 suits subscription rate limits.

### Tiers

Two presets cover the usual runs:

```sh
uv run scripts/run.py --tier release --agent claude-code   # before a release, once per agent
uv run scripts/run.py --tier release --agent codex
uv run scripts/run.py --tier fast                          # after editing a skill (make eval-fast)
```

- `release` runs `engineeringMaturity` and `rules` with the bare, stub, and
  consult arms, 3 attempts, and the judge. It saves the baseline `runs/baselines/release-<agent>.json`.
- `fast` runs Claude Code on the tasks that exercise the skills changed since
  `--changed-since` (default `HEAD`, which includes uncommitted edits). It
  takes at most `--max-tasks` (default 4), preferring tasks with fewer
  intended skills, and falls back to `core` when no task matches. It runs
  the consult arm only, 3 attempts, without the judge. It reuses the bare arm
  of `release-claude-code` and compares its Consult arm with the baseline's.

A baseline is reused only when the agent, model, effort, CLI version, and a
hash of every selected task directory match. Otherwise `run.py` prints the
reason and runs the bare arm. `--baseline` and `--save-baseline` name a
baseline explicitly.

The fast tier catches skill-loading failures and large regressions. With 3
attempts per task and a per-task reward SD of about 0.15, it cannot resolve a
change smaller than about 0.3. The release tier's 15 tasks at 3 attempts
resolve a suite lift of about 0.1.

### Reference ablation

`--drop-references code-review,ui-design` runs the consult arm without those
skills' `references/` directories; the SKILL.md bodies still name the files.
Write a suite file under `eval/suites/` listing the tasks whose trials opened
those references (`scripts/reference_reads.py` shows which), then run it on
the fast tier with `--suite`. `run.py` stops unless a reusable baseline's
consult arm ran today's full pack, so the lift report's comparison against
that arm measures the dropped references and no other skill edit. An ablation
never saves a baseline. With 3 attempts and no judge, the fast tier resolves
only large changes, so "no difference" is weak evidence that a reference is
not needed.

### Stub arm

The stub arm separates what the skills say from the fact that they are
installed. It gets the consult arm's hook and the same skill names and
descriptions, but every skill body reads "This skill has no further
guidance." `scripts/stub.py` builds it under `runs/stub-skills/`.

- Stub minus bare: what the listing and the hook change on their own. The
  hook prints the Consult core (`agents/.agents/core.md`), so this
  includes the always-on core rules.
- Consult minus stub: what the skill bodies add beyond the core. Codex arms
  get no hook, and v2 ships no skill copy of the core, so on Codex the
  consult arm runs without the core until a Codex install path exists.

Both arms read one snapshot of `agents/.agents/skills` taken when the run
starts, so an edit made mid-run reaches neither.

### Placebo arm

The placebo arm separates what the Consult core says from the effect of
printing any rules at all. It is the stub arm with one change: its hook prints
`placebo/core.md` in place of the Consult core. That file keeps the core's
opening paragraph byte for byte, so skill loading matches the stub arm. Below
it are formatting rules with the core's sections, rule counts, and length
(within 5% of its words), on matters no check, probe, rubric item, or judge
criterion scores. `scripts/placebo.py` builds the hook settings under
`runs/placebo-hooks/` with the function that writes `plugin/hooks/hooks.json`.

- Stub minus placebo: what the core's content adds beyond any rules.
- Placebo minus bare: what printing a core of that size changes on its own.

No tier runs it; name it with `--arms bare,stub,placebo,consult`. It needs an
agent with a hook (`consult_settings`), so Codex cannot run it. `lift.py
--placebo` reports placebo vs bare, and stub vs placebo when `--stub` is also
given. When `core.md` changes, keep the placebo's shape in step: a test in
`verifier/tests/test_placebo.py` compares the two.

### Trigger suite

```sh
uv run scripts/triggers.py --wiring-check --arms plugin,skills,bare   # no model call
uv run scripts/triggers.py --attempts 3                                # make eval-triggers
```

The trigger suite checks whether Claude Code loads the right Consult skill at
the right time. `triggers/cases.yaml` holds 20 positive cases, where a named
skill should load before the first write. It also holds 8 negative cases:
typo fixes, questions, and test runs, where no Consult skill should load.
Each trial runs `claude -p` once in a container built from the case's
workspace.

- `plugin`: this repo's `plugin/` loaded with `--plugin-dir`, as a real
  install loads it, so skills appear as `consult:<name>`. `--plugin <dir>`
  tests a variant.
- `skills`: Harbor's wiring, with plain names and the hook through
  `--settings`. Comparing it with `plugin` shows whether Harbor results carry
  over to a real install.
- `bare`: the control.

A positive trial stops at the agent's first write. A load counts when a
Skill call or a SKILL.md read for a catalog skill succeeds before that write.
The thresholds sit in `cases.yaml` and are fixed before a run:

- Focused rate: at least 0.80 of positives load at most 2 Consult skills before the first write.
- Narrow recall, one of the case's `required_any` skills: at least 0.73.
- False-trigger rate on negatives: at most 0.08, and no negative may trigger
  in 2 of its attempts.

The report gives each rate with a 90% Wilson interval. The script exits 1
when a Consult arm fails or has no usable data.

`--suite` runs another cases file with the same rules:

- `triggers/generalization.yaml`: 12 positives and 6 negatives, written by an
  agent that never saw the skill descriptions or the hook. Use it to check
  that a description change generalizes beyond the prompts it was tuned on.
- `triggers/borderline.yaml`: 8 requests with no agreed answer, such as a
  one-line port change, a dependency bump, or a commit-only request. Every
  case is marked negative, so a "false trigger" there only means that Consult
  loaded. Read the loads per case; the pass line is not a verdict. Results and every transcript
land in `runs/triggers/<timestamp>-<label>/`. The token reaches the container
by name only. `--wiring-check` runs without it: Claude Code prints its skill
list and hook events before it fails at auth.

### Reading the lift report

Consult aims to raise the floor of engineering maturity, so the report shows
the low end next to the mean:

- **Floor rate**: the share of trials that failed verification or scored
  below 0.5.
- **p25**: the 25th-percentile reward per arm.
- **Intervals**: suite lift and floor-rate change each carry a 90% bootstrap
  interval over trials resampled within each task. An interval that contains
  0 is labelled "not distinguishable from noise".
- **Cost and effort**: each arm's mean output tokens, cost, agent seconds,
  turns, lines changed, and questions asked, with the change and its interval.
  Questions count agent messages that end in a question after the last user
  turn, the gate-fatigue number. Cost is the agent's API-equivalent estimate,
  since runs bill a subscription. A resumed multi-step trial reports its final
  step's tokens, which already include the earlier steps, and no cost, until
  a real trial shows whether Harbor's per-step cost covers one step or all.
- **Size per stage** and **Simplicity parts per stage**: for a staged task,
  each arm's means per stage, as `bare / consult`. The first table gives
  non-blank lines of source, test, and spec or docs files (Markdown, OpenAPI,
  and schema files) in the tree the stage left. The second gives the five
  parts that `core.simple.s<k>` averages, which shows which part moves. Each
  `core.simple.s<k>` check writes its stage to `stage-shape.json` beside
  `reward-details.json`; it changes no reward. A stage that built nothing
  beyond the scaffold counts toward the lines but not the parts. An offline
  rescore has no step snapshots, so its trials record only the final stage.

When a task's trials do not all carry the same model scores, as in a fast
run against a release baseline, an old generic-judge job against a rubric
job, or a trial whose judges failed, that task is rescored from its
deterministic dimensions in both jobs. `lift.py --baseline-consult <job>` adds the same
comparison between an earlier Consult job and this one. `lift.py --stub <job>`
adds consult against stub and stub against bare, with a verdict on skill
content. A trial without a reward in either job withholds the verdict.

Judge routing: code tasks are judged by the rubric judges (see
[Rubric judges](#rubric-judges)). Routing tasks keep RewardKit's `claude-code`
agent judge running `claude-sonnet-5` through the subscription token. It installs the
Claude Code CLI in the verifier container, because Anthropic answers a
subscription token sent straight from LiteLLM with a bare 429. Set
`CONSULT_EVAL_JUDGE=openai/gpt-5.5` and pass `--ve OPENAI_API_KEY=...` to use
another provider as a plain LLM judge for routing tasks; the rubric judges
always run on Claude. Set
`CONSULT_EVAL_SKIP_JUDGE=1` to score deterministic dimensions only. When the
environment holds no judge credential, the verifier skips the judges and the
reward excludes them.

## Suites and tasks

Suites live in `suites/*.yaml` and list task names. Tasks live in
`tasks/<name>/` in Harbor's task format:

```text
tasks/<name>/
  task.toml                 name, kind, features, timeouts, judge env, [[steps]]
  instruction.md            the prompt the agent receives (single-step tasks)
  steps/<name>/             instruction.md per turn, and solution/ (multi-step tasks)
  environment/Dockerfile    synced; Node 22, git, python3, rewardkit
  environment/workspace/    the starting repository, committed at build time
  solution/solve.sh         oracle reference (routing: no-op)
  tests/
    consult.json            kind, intended skills, visible test command
    hidden.mjs              hidden implementation check (code tasks)
    rules_probe.mjs         runtime probe some rule checks read (when present)
    proof/submitted.py      per-task submitted-proof regex
    ...                     synced dimension scripts, judge prompts, and rubric items
```

Two kinds of task exist. `code` tasks change a small Node repository; their
score covers verification, proof, change quality, and the rubric judges.
`routing` tasks ask for a read-only planning note; their score covers an
untouched workspace plus the generic judge.

- `smoke`: one routing task, for wiring checks.
- `core`: always-on and core design skills (4 tasks).
- `allSkills` / `engineeringMaturity`: every skill at least once (12 tasks).
- `routing`: the four read-only planning tasks.
- `largeProject` / `linkShortener`: larger cross-file tasks.
- `regressionCheck`: tasks that once regressed under Consult.
- `rules`: underspecified tasks scored per skill rule (3 tasks).
- `houseStyle`: one project built in five stages plus a control, scored per
  house default and on simplicity at each stage (2 tasks).

Prompts and starting repositories never name Consult or a skill. The intended
skills for a task live in `tests/consult.json` and feed only the trigger-rate
readout and the skills scorecard.

### Rule tasks

The `rules` suite measures whether each skill's rules change what the agent
does. Its prompts are product briefs or user reports, not specs, so a pass
means the agent noticed a requirement the prompt never stated.

- `bug-from-symptom`: a customer report that names no file. One step.
- `money-field-change`: multi-currency orders in a service whose `total` field
  an iOS app reads. Three steps.
- `service-from-brief`: a link shortener built from an empty repository. Three
  steps.

A multi-step task lists `[[steps]]` in `task.toml`. The `brief` step sends the
product brief. The `approve` step sends a fixed reply: "Approved, including the
interface and data shapes you proposed. Build it. Use your recommended option
for anything still open." Consult's `human.1` has a second checkpoint: the agent
shows the data shapes and contracts it wrote, with their checks, before building logic. The
`continue` step answers it: "Approved. Continue." An agent that built
everything in the `approve` step gets the same reply. The agent fragments set
`resume_trajectory: true`, so each step continues the same session.

A rule task adds these keys to `tests/consult.json`:

- `rules`: the rule ids the task scores, such as `api.1` for Rule 1 of `api`.
- `expect_silent`: skills the agent should not read on this task.
- `gated_paths`: paths that must not change before the approval turn.
- `test_file_cmd`: runs only the agent's own test files, for `proof.2`.

### House style suite

`houseStyle` asks whether Consult builds the way its house defaults say and
keeps the code simple as it grows. Bare Claude Code already passes the
correctness tasks above, so those cannot show this. Here the checks score
which side the agent picked where several approaches are sound.

```sh
uv run scripts/run.py --suite houseStyle --agent claude-code --arms bare,consult --attempts 3 --skip-preflight
```

- `staged-commissions` builds one service in five stages, each a brief, an
  approval, and a continue turn (15 steps): commissions and their lifecycle,
  withdrawal with a restocking fee, patron accounts, prices from an FX
  provider, and a deposit change that cuts across the earlier stages. The
  hidden check reruns every stage's acceptance tests on the final tree, so a
  later stage that breaks an earlier one fails.
- `follow-the-project` is the control: a repository that already uses
  classes, thrown error classes, layer folders, and a `test/` folder.
  `default.follow` scores whether the change matches those choices. A drop
  under Consult means the house defaults override projects they should yield
  to.

The rule checks live in `verifier/shared/house_rules.py`. The static ones read
facts that `verifier/shared/code_shape.mjs` extracts with the TypeScript
compiler API, pinned in `verifier/analyzer/package.json` and installed into
the image at `/opt/eval/analyzer`. Shape scores are fractions of functions,
logic decisions, or files, so a larger change scores no worse for its size,
only for how it is built:

| id | measures |
|---|---|
| `core.simple` | mean of the five shape scores below, on the final tree |
| `core.simple.s1`..`s5` | the same, on the tree each stage left (step-verifier snapshots in `/opt/eval/snapshots`) |
| `core.4` | share of functions within 30 lines, nesting under three levels, compound conditions named |
| `core.1` | share of logic decisions (real conditions, loops, switch cases; not null checks or Result plumbing) in pure functions |
| (part of `core.simple`) | share of files without mutated module state or stateful classes; no import cycles; no single-implementation interface or abstract class |
| `default.1`, `default.2`, `default.4`, `default.5` | static: no stateful classes or inheritance; feature folders and colocated tests; Result values, with plain `Error`/`TypeError`/`RangeError` throws counted as bug checks; state variants and Zod parsing |
| `default.9`, `default.10`, `core.untrusted` | rule probe against a fake FX provider that hangs, fails once, fails for good, or sends garbage, plus malformed requests. `default.9` wants a timeout and no retry on a permanent failure; a build that retries the transient failure also needs jitter beside the outbound call, and one that does not retry needs none. `default.10` is the share of failure responses carrying a correlation id |
| `core.untrusted`, `default.tooling` | readouts kept after core rule 6 and default 11 were cut, so a later run shows whether the cuts cost anything: untrusted input rejected (probe), and one lockfile, the four check scripts, and a pinned language version |
| `default.7`, `human.1.stages`, `human.7`, `proof.6` | per stage, from the trajectory: contract written first, the brief turn stopped at the plan, the report order, a test seen failing |

A staged task adds `stages`, `steps_per_stage`, `stage_headings` (each brief's
first line, which splits the trajectory into stages),
`allowed_env`, and `probe_timeout` to `tests/consult.json`. The control adds
`shape_scope: changed` and `project`. Each task's oracle builds a reference in
the intended style; `verifier/tests/test_house_rules.py` checks that the
reference scores high and a typical layered, class-based, throwing variant
scores low.

### Follow-up change test

The house-style checks score conformance to Consult's own defaults. The
follow-up test asks a question Consult did not define: is the code one arm
leaves behind cheaper for someone else to change? A bare agent in a fresh
session makes a held-out sixth change to each arm's final
`staged-commissions` tree.

```sh
uv run scripts/followup.py build runs/<bare-job> runs/<consult-job>   # needs Docker
harbor run -c runs/followup/<stamp>/job.json --yes                    # the command build prints
uv run scripts/followup.py report runs/<followup-job>
```

- `build` writes one single-step task under `runs/followup/<stamp>/` per
  `staged-commissions` trial whose verification passed. The starting tree is
  the trial's final tree, rebuilt as `rescore.py` rebuilds it, and committed
  as the scaffold, so the follow-up diff holds only the sixth change. The
  instruction is `followup/staged-commissions/instruction.md`: a discount for
  returning patrons that cuts across pricing, withdrawal, accounts, and
  currency. `job.json` runs every task with the agent's bare arm.
- The verifier scores the visible tests and
  `verifier/hidden/staged-commissions-followup.mjs`. That check reruns the five
  stage checks unchanged, then checks stage 6 through the HTTP API alone. No
  Consult rule, rubric, or shape score runs.
- `report` prints, per source arm, the pass rate, output tokens, agent
  seconds, files touched, and lines changed, with the change and a 90%
  bootstrap interval from `lift.py`. Trials are pooled per arm. A trial
  without a reward counts as a fail. Files and lines come from the follow-up
  trial's `judge-bundle.md`.

The oracle for the sixth change lies over the stage-5 reference, in
`followup/staged-commissions/solution/overlay`.
`verifier/tests/test_followup.py` runs the check with Node: the oracle passes
all six stages, and the unmodified reference passes stages 1 to 5 and fails
stage 6.

## Scoring

RewardKit combines dimension scores with `tests/reward.toml`. The weights keep
the split from the previous harness: 55 percent deterministic, 45 percent
model-judged.

| Dimension | Kind | Weight | What it measures |
| --- | --- | ---: | --- |
| `verification` | code | 0.275 | Visible `npm test` and the hidden check both pass |
| `proof` | code | 0.1925 | 1.0 submitted proof and a post-write test command, 0.85 submitted only, 0.6 post-write only, 0.35 verification passed, else 0.15 |
| `change_quality` | code | 0.0825 | 1.0 source and tests changed, 0.7 source only, else 0.25 |
| `no_file_writes` | routing | 0.55 | Workspace unchanged and no write tool calls |
| `rubric` | code | 0.45 | The task's rubric items: must-have met rate x 0.6 plus quality met rate x 0.4, unknown answers left out. Dropped until the task has a rubric |
| `judge` | routing | 0.45 | Claude Code judge, four numeric criteria: engineering maturity 0.35, proof quality 0.25, simplicity 0.2, risk handling 0.2 |
| `skill_triggering` | both | 0 | Share of intended skills the agent read or invoked |
| `non_interruption` | both | 0 | 1 minus 0.25 per agent message after the last user turn that ends with a question |
| `rules` | both | 0 | One criterion per rule id in `consult.json` `rules` |

The zero-weight readouts stay in `reward.json` for regression tracking without
distorting lift. The bare arm reads no skills by construction, so the consult
arm's `skill_triggering` is also the check that injection worked.

Each rule check in `verifier/shared/consult_rules.py` tests one numbered rule
of one SKILL.md. It reads the trajectory, the diff against the scaffold commit,
or a per-task probe. A check that an idle agent would pass, such as
`documentation.1`, scores 0 unless verification passed. A check returns
None when the trial gave its rule nothing to act on, such as a commit rule in
a trial with no commit: the id goes to `rules-na.json` and `lift.py` leaves
that trial out of the rule's mean and its `n`. Per-rule scores land in
`reward-details.json`. `rules` stays at weight 0 until a sample of hand
ratings calibrates the checks. `scripts/rule_labels.py export <sheet.csv>
<job>...` writes one row per rule verdict with the rule's text and the trial
evidence dir to read; it leaves out sign-off rules and never overwrites a sheet. A
reviewer writes `pass` or `fail` in the `human` column, and
`rule_labels.py agree <sheet.csv>` reports how often each check matched, with
its false passes and false fails. Tasks
that score no rules get `rules = 0.0` in their `reward.toml`, so a calibrated
weight reaches only the tasks that list rules.

In a multi-step task the `brief` step runs its own verifier, the `signoff`
suite, which scores the task's sign-off rule, such as `human.1`:

- 1 when no gated path changed.
- 1 when the agent built but flagged the result as provisional. Consult now
  asks an agent with nobody to answer to stop at the gate, but a headless
  agent cannot know a reply is coming, so a flagged build still passes.
- 0 for a silent build.

`multi_step_reward_strategy = "final"` keeps the sign-off score out of the
trial reward. A step between the first and the last runs a synced placeholder
verifier that records 0, so the judge runs once, after the final step.

After the lift and cost tables, `lift.py` prints two scorecards:

- The pass rate per rule for each arm. A sign-off score counts only when the
  build step's verification passed.
- Per task, the skills the Consult arm read, missed, or read despite
  `expect_silent`, and each arm's sign-off mode: `stopped`, `provisional`, or
  `built`.

`scripts/reference_reads.py <job>...` prints, per job, the share of trials
that opened each skill reference file. A file nobody opened reads 0, which
the reference audit weighs against its upkeep.

`scripts/charts.py <summary.json> <out_dir> "<agent>"` draws the release
chart from a `lift.py` summary: each scored task's reward for the bare and
Consult arms, as `release-lift-<agent>-light.svg` and `-dark.svg`. Its footer
notes any task left out, failed trial, or judge exclusion. Regenerate it from
each release's summary instead of editing the SVGs.

The routing tasks' judge receives the task instruction and a bundle with the
git diff, new files, and the agent's final message. `consult_lib.py prepare`
writes both into the prompt, so the `claude-code` judge scores in one turn at
low effort (`CLAUDE_CODE_EFFORT_LEVEL` in `test.sh`). It does not receive the
trajectory. Reading the trajectory with tool calls cost about 440k input
tokens per trial, and the `proof` dimension already scores the process from
it. The criteria and prompt are `verifier/shared/judge/quality.toml` and
`prompt.md`.

The task image preinstalls the Claude Code and Codex CLIs at the versions
pinned in `agents/*.yaml`, so Harbor skips its install and the judge reuses
`claude`. Change the version in both the Dockerfile and the agent fragment.

## Editing the verifier

Harbor uploads only a task's own `tests/` directory, so the sync script copies
the shared verifier code into every task. Edit the source under `verifier/`
and resync:

```sh
uv run scripts/sync_tests.py          # copy shared files into every task
uv run scripts/sync_tests.py --check  # fail on drift; run in CI and `make eval`
```

- `verifier/shared/consult_lib.py`: trajectory parsing, git helpers, judge
  bundle, and the `prepare` step that drops a judge when it cannot run.
- `verifier/shared/judge_runner.py`: the rubric judges (see below).
- `verifier/shared/rubric/`: the rubric dimension (`score.py`) and the judge
  prompts: `system.md` for every judge and one `<dimension>.md` per judge.
- `verifier/shared/consult_rules.py`: the rule checks, keyed by rule id.
- `verifier/shared/<dimension>/`: one RewardKit script per dimension.
- `verifier/hidden/<task>.mjs`: the hidden check for each code task, keyed by
  task name.
- `verifier/hidden/<task>.rules.mjs`: a runtime probe for rule checks. It
  prints `{"<rule id>": 0|1}` as its last line.
- `verifier/rubrics/<task>.json`: the task's judge rubric (see below). The
  sync validates it and writes the resolved items to `tests/rubric/items.json`.
- `verifier/rubrics/core_items.json`: shared rubric item templates.
- `verifier/rules.json`: every rule of every skill, marked `check`,
  `judge-only`, or `untested`. `scripts/validate_skill_anatomy.py` fails when
  a rule has no entry, an entry names a rule that no longer exists, or a
  `check` entry has no function in `consult_rules.py`. Renumbering a skill's
  rules therefore means updating this file.

Every rule check has a passing and a failing fixture:

```sh
python3 -m unittest discover verifier/tests
```

To add a task:

1. Copy a task directory of the same kind.
2. Replace `instruction.md` and `environment/workspace/`.
3. Edit `tests/consult.json`.
4. For a code task, write `verifier/hidden/<task>.mjs`, `tests/proof/submitted.py`,
   `solution/solve.sh`, and a rubric in `verifier/rubrics/<task>.json`.
5. For a rule task, add the rule-task keys to `consult.json`. A multi-step
   task also needs `steps/brief/`, `steps/approve/`, `steps/continue/`, and a
   no-op `solution/solve.sh` in `brief` and `continue`, so the oracle proposes
   first and builds once, in `approve`.
6. Add the name to a suite and run the sync.

### Judge rubrics

A rubric is the checklist the code judges answer for one task: 12 to 20
atomic items, each a yes/no question tied to the Consult rules it applies. A
readout rubric (`"readout": true`, 1 to 6 items) scores rules a check cannot
read. Its weight
is 0, so the task reward does not move, and `lift.py` reports its answers per
rule as `judge` rows.
"Yes" always means the item is met, so a negative item starts with
"Does NOT". Each item has:

- `id`: a dotted slug, such as `scope.no_new_env`.
- `dimension`: one of `structure`, `scope`, `boundaries`, `proof`, `report`.
  Each dimension has its own isolated judge.
- `rules`: the rule ids the item applies, such as `core.2`.
- `key_phrase`: a phrase quoted verbatim from one of those rules.
- `question`, `look_at`, `yes_when`, `no_when`: what the judge answers, where
  it looks, and what decides each answer.
- `polarity`: `positive` or `negative`.
- `tier`: `must` (the reference solution must meet it) or `quality`.

An item can name a template from `verifier/rubrics/core_items.json` with
`extends`, then fill the template's `{placeholders}` with the task's
specifics, such as the calculation's name or the expected config:

```json
{"id": "scope.no_new_env", "extends": "scope.no_unrequested_surface",
 "question": "Does NOT add any route, command, flag, config key, environment variable, or startup requirement beyond `PORT` and `DATABASE_URL`?"}
```

The sync stops on any problem `scripts/rubric.py` finds, for example:

- an unknown rule id;
- a key phrase that is not verbatim in its rule;
- an unfilled placeholder;
- a negative item that does not ask "Does NOT";
- duplicate ids;
- fewer than 12 or more than 20 items;
- no must-have item.

Only code tasks have rubrics.

### Rubric judges

When a code task has a rubric, `test.sh` runs `judge_runner.py` before
RewardKit. It starts one `claude -p` call per dimension that has items, two
at a time. Each call gets:

- the shared `system.md` prompt, and its own `<dimension>.md` guidance;
- the task instruction and only its own items, without their tier or the
  rule's key phrase (the Consult arm often repeats rule wording, and a judge
  shown it would reward the echo);
- on a multi-step task, the agent's reply that each later turn answered, such
  as the proposal the user approved;
- the changed paths with their git status, then the agent's changes (the diff
  plus new files), fenced as data;
- a blinded copy of the final workspace as its working directory, to read
  with Read, Grep, and Glob.

Only the report judge also sees the agent's final message, so the agent's
description of its code cannot sway the judges of the code. Each judge answers
every item yes, no, or unknown, with a `path:line` quote as evidence. Something
the judge searched for and did not find is a definite answer, not unknown.

The blinded copy leaves out `.git`, `node_modules`, symlinks, and files over
1 MB. It renames `CLAUDE.md`, `AGENTS.md`, and `.claude/` so the judge does
not load them, and moves `docs/plans/` to `docs/notes/`. In every text file,
the changes, and the final message, it replaces Consult's names for its own
parts (Consult, core rule N, Iron Law, skill names and paths, fresh-context)
with "the project conventions", which the bare arm could also write. Both arms
get the same replacements.

The call is locked down: `--restricted` removes every tool that runs commands
and loads no user or project settings, so no hook or plugin runs. It also
passes `--strict-mcp-config`, `--disable-slash-commands`, `--permission-mode
dontAsk`, `--no-session-persistence`, and a turn cap. It runs with an empty
home directory and one credential, the subscription token when one is set.
`--bare` is not used, because it cannot read a subscription token. The agent
ran as root in the same container, so the runner refuses to start the judges
when a `CLAUDE.md`, `AGENTS.md`, or `.claude` sits in a parent of the view, or
a managed settings directory exists.

A failed call is retried once. The answers, each call's errors, attempts,
turns, and usage go to `/logs/verifier/judge-items.json`, and each attempt's
message stream to `/logs/verifier/judge/<dimension>.<attempt>.jsonl` for
reading transcripts. An item the judge skipped or answered outside the schema
counts as unknown. When a call still fails, or no item gets a yes or no, the
trial gets no rubric score and the reward drops the rubric dimension. `lift.py`
then compares that task without model scores in both jobs, so a failed judge
never mixes deterministic-only rewards with judged ones. Rescoring keeps the
original answers and transcripts beside the kept score.

`judge_runner.py` reads these settings from its environment:
`CONSULT_JUDGE_MODEL` (default `claude-opus-5-5`), `CONSULT_JUDGE_EFFORT`
(`high`), `CONSULT_JUDGE_MAX_TURNS` (30), `CONSULT_JUDGE_TIMEOUT_SEC` (900 per
call), and `CONSULT_JUDGE_CONCURRENCY` (2). A Harbor trial passes the verifier
only what `task.toml` lists under `[verifier.env]`, so trials use the
defaults.

Code tasks give each agent turn 45 minutes and the verifier 60 minutes. Both
are generous on purpose: a cut-off Opus turn, or a judge stopped mid-read,
would score the harness instead of the agent.

Check the task with the oracle before spending model calls:

```sh
harbor run -p tasks -i <task> -a oracle -o runs --yes
```

Then check the rubric against the oracle. `scripts/oracle_judge.py` applies
each task's `solution/solve.sh` in the task image, checks it passes the
visible tests and the hidden check, and runs the rubric judges on every
dimension but report, since the oracle writes no final message. Every
must-have item must answer yes. One that does not is a bug in the rubric or
the oracle. A multi-step task's judges also read the reply each later turn
answered, so its oracle keeps that reply, such as the approved proposal, in
`steps/<step>/solution/reply.md`, and the check passes it to them.

```sh
uv run scripts/oracle_judge.py --tasks <task>            # print the judge call count
uv run scripts/oracle_judge.py --tasks <task> --dry-run  # apply and check the oracle, no judge
uv run scripts/oracle_judge.py --tasks <task> --yes      # run the judges (bills the subscription)
```

Results go to `runs/oracle-judge/<timestamp>/`.

### Calibrating the judges

A rubric dimension carries a claim only after its judge agrees with the
maintainer. Saved trials are judged again offline, then a sample of answers is
hand-labelled.

`scripts/rescore.py --rejudge` rebuilds each trial's final workspace, as a
plain rescore does, and runs the verifier with the subscription token, so the
rubric judges answer as in a live run. The trial takes the new rubric score;
the original judge score is dropped. Trials run one at a time, because the
runner already makes two calls at once. Without `--yes` it prints the call
count and stops. Output goes to `<job>-rejudged/`, or `<job>-<suffix>/` with
`--suffix`, so a repeat pass can sit beside the first. The task environment
check compares each trial's start with the last commit that touched the
task's `environment/`, so a fresh checkout or worktree can rescore old runs.

```sh
uv run scripts/rescore.py runs/<job> --rejudge             # print the judge call count
uv run scripts/rescore.py runs/<job> --rejudge --dry-run   # rebuild the workspaces, no judge
uv run scripts/rescore.py runs/<job> --rejudge --yes       # run the judges (bills the subscription)
```

`scripts/judge_labels.py` turns the rejudged jobs into a blind label sheet:

```sh
uv run scripts/judge_labels.py export runs/labels/judge.csv runs/<bare-job>-rejudged runs/<consult-job>-rejudged
uv run scripts/judge_labels.py agree runs/labels/judge.csv
uv run scripts/judge_labels.py repeat runs/<job>-rejudged runs/<job>-rejudged-repeat
```

`export` samples 50 answers per dimension by default, half from each arm and
spread across tasks. The sheet shows each item, but not the judge's answer,
reason, or evidence (whose form gives the answer away), nor the arm. Each case's request,
earlier replies, diff, and final message are in `<sheet>-cases/<case>.md`,
scrubbed as the judges' view is. The hidden fields go to `<sheet>.key.json`.
Write `yes` or `no` in the `human` column. `agree` reports per dimension
Cohen's kappa against the judge, each arm's bias (the judge's yes-rate minus
the human's), and the judge's unknown rate. `repeat` reports how often two
rejudge passes give the same answer. A dimension passes the gate with kappa
at least 0.7, each arm's bias under 0.1 in size, unknown under 10%, and
repeat agreement at least 0.9.

## Known gaps

- `large-checkout-workflow` and `large-link-shortener` have no `solution/`
  and no rubric, so neither `-a oracle` nor `oracle_judge.py` can check them.
- The oracle leaves no trajectory, so trajectory-based rules such as `api.1`
  and `proof.2` score 0 on it.
- Rule checks are heuristics until calibrated. `proof.2` misses a fix that
  renames the source file it repairs. `api.1` skips schema, migration, and
  model files by name, so it still counts a data-stage edit as handler code
  when the file also renders responses, as `money-field-change`'s
  `src/orders.js` does. It also skips a request-validation schema, which
  belongs to the contracts stage.
- The question readout counts only questions after the `continue` turn, so it
  misses a needless question asked in `approve`. One `continue` turn answers
  one more gate; an agent that splits the work into behavior slices can stop
  at a later gate and leave the build unfinished.
- The previous harness could execute the migration in a real Postgres given
  `CONSULT_EVAL_POSTGRES_URL`. The Harbor port checks the SQL text only.
- `routing-settings-copy` listed `accessibility` as a feature. It is not a
  shipped skill, so the intended list leaves it out.
- Harbor injects the canonical skills as plain user skills. For Claude Code,
  the consult arm also installs the plugin's SessionStart hook through the
  `consult_settings` key in `agents/claude-code.yaml`, which `run.py` passes as
  Claude's `--settings` file. Without the hook, Claude loaded no Consult skill
  in any consult-arm trial. The trigger suite's `plugin` arm covers the real
  install.
- With the hook, Sonnet 5 at medium effort loaded a Consult skill in 2 of 19
  consult-arm trials on the `rules` suite (2026-09-24), and in 6 of 9 at high
  effort. The +0.141 lift from those runs came with almost no skill loaded, so
  it measures the listing and the hook. The agent fragment now runs Opus 5.5
  at `xhigh`. Those runs predate the always-on core: the hook then printed
  only a routing line, so later results are not comparable on this point.
- Harbor's Codex agent takes the newest session file as the trajectory and
  resumes the next step with `--last`. Both pick a subagent when Codex spawns
  one, so `agents/codex.yaml` turns `multi_agent` off. Codex's consult arm
  therefore cannot hand review to a subagent, which `code-review` prefers.
