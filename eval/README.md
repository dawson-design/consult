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

### Stub arm

The stub arm separates what the skills say from the fact that they are
installed. It gets the consult arm's hook and the same skill names and
descriptions, but every skill body reads "This skill has no further
guidance." `scripts/stub.py` builds it under `runs/stub-skills/`.

- Stub minus bare: what the listing and the hook change on their own.
- Consult minus stub: what the skill bodies add.

Both arms read one snapshot of `agents/.agents/skills` taken when the run
starts, so an edit made mid-run reaches neither.

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

- Workflow recall on code-changing positives: at least 0.83.
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

When one job has judge scores and the other does not, as in a fast run
against a release baseline, both are rescored from their shared
deterministic dimensions. `lift.py --baseline-consult <job>` adds the same
comparison between an earlier Consult job and this one. `lift.py --stub <job>`
adds consult against stub and stub against bare, with a verdict on skill
content. A trial without a reward in either job withholds the verdict.

Judge routing: the default judge is RewardKit's `claude-code` agent judge
running `claude-sonnet-5` through the subscription token. It installs the
Claude Code CLI in the verifier container, because Anthropic answers a
subscription token sent straight from LiteLLM with a bare 429. Set
`CONSULT_EVAL_JUDGE=openai/gpt-5.5` and pass `--ve OPENAI_API_KEY=...` to use
another provider as a plain LLM judge. Set
`CONSULT_EVAL_SKIP_JUDGE=1` to score deterministic dimensions only. When the
environment holds no judge credential, the verifier skips the judge and the
reward excludes it.

## Suites and tasks

Suites live in `suites/*.yaml` and list task names. Tasks live in
`tasks/<name>/` in Harbor's task format:

```text
tasks/<name>/
  task.toml                 name, kind, features, timeouts, judge env, [[steps]]
  instruction.md            the prompt the agent receives (single-step tasks)
  steps/<name>/             instruction.md per turn, and solution/ (two-step tasks)
  environment/Dockerfile    synced; Node 22, git, python3, rewardkit
  environment/workspace/    the starting repository, committed at build time
  solution/solve.sh         oracle reference (routing: no-op)
  tests/
    consult.json            kind, intended skills, visible test command
    hidden.mjs              hidden implementation check (code tasks)
    rules_probe.mjs         runtime probe some rule checks read (when present)
    proof/submitted.py      per-task submitted-proof regex
    ...                     synced dimension scripts and judge rubric
```

Two kinds of task exist. `code` tasks change a small Node repository; their
score covers verification, proof, change quality, and the judge. `routing`
tasks ask for a read-only planning note; their score covers an untouched
workspace plus the judge.

- `smoke`: one routing task, for wiring checks.
- `core`: always-on and core design skills (4 tasks).
- `allSkills` / `engineeringMaturity`: every skill at least once (12 tasks).
- `routing`: the four read-only planning tasks.
- `largeProject` / `linkShortener`: larger cross-file tasks.
- `regressionCheck`: tasks that once regressed under Consult.
- `rules`: underspecified tasks scored per skill rule (3 tasks).

Prompts and starting repositories never name Consult or a skill. The intended
skills for a task live in `tests/consult.json` and feed only the trigger-rate
readout and the skills scorecard.

### Rule tasks

The `rules` suite measures whether each skill's rules change what the agent
does. Its prompts are product briefs or user reports, not specs, so a pass
means the agent noticed a requirement the prompt never stated.

- `bug-from-symptom`: a customer report that names no file. One step.
- `money-field-change`: multi-currency orders in a service whose `total` field
  an iOS app reads. Two steps.
- `service-from-brief`: a link shortener built from an empty repository. Two
  steps.

A two-step task lists `[[steps]]` in `task.toml`. The `brief` step sends the
product brief. The `approve` step sends a fixed reply: "Approved, including the
interface and data shapes you proposed. Build it. Use your recommended option
for anything still open." The agent fragments set `resume_trajectory: true`, so
the second step continues the same session.

A rule task adds these keys to `tests/consult.json`:

- `rules`: the rule ids the task scores, such as `api.1` for Rule 1 of `api`.
- `expect_silent`: skills the agent should not read on this task.
- `gated_paths`: paths that must not change before the approval turn.
- `test_file_cmd`: runs only the agent's own test files, for `debugging.5`.

## Scoring

RewardKit combines dimension scores with `tests/reward.toml`. The weights keep
the split from the previous harness: 55 percent deterministic, 45 percent
judge.

| Dimension | Kind | Weight | What it measures |
| --- | --- | ---: | --- |
| `verification` | code | 0.275 | Visible `npm test` and the hidden check both pass |
| `proof` | code | 0.1925 | 1.0 submitted proof and a post-write test command, 0.85 submitted only, 0.6 post-write only, 0.35 verification passed, else 0.15 |
| `change_quality` | code | 0.0825 | 1.0 source and tests changed, 0.7 source only, else 0.25 |
| `no_file_writes` | routing | 0.55 | Workspace unchanged and no write tool calls |
| `judge` | both | 0.45 | Claude Code judge, four numeric criteria: engineering maturity 0.35, proof quality 0.25, simplicity 0.2, risk handling 0.2 |
| `skill_triggering` | both | 0 | Share of intended skills the agent read or invoked |
| `non_interruption` | both | 0 | 1 minus 0.25 per agent message after the last user turn that ends with a question |
| `rules` | both | 0 | One criterion per rule id in `consult.json` `rules` |

The zero-weight readouts stay in `reward.json` for regression tracking without
distorting lift. The bare arm reads no skills by construction, so the consult
arm's `skill_triggering` is also the check that injection worked.

Each rule check in `verifier/shared/consult_rules.py` tests one numbered rule
of one SKILL.md. It reads the trajectory, the diff against the scaffold commit,
or a per-task probe. A check that an idle agent would pass, such as
`documentation.1`, scores 0 unless verification passed. Per-rule scores land in
`reward-details.json`. `rules` stays at weight 0 until a sample of hand
ratings calibrates the checks.

In a two-step task the `brief` step runs its own verifier, the `signoff`
suite, which scores the task's sign-off rule, such as `domain-modeling.10`:

- 1 when no gated path changed.
- 1 when the agent built but flagged the result as provisional. `workflow`
  Rule 7 asks for that when no human can answer, and a headless agent cannot
  know a reply is coming.
- 0 for a silent build.

`multi_step_reward_strategy = "final"` keeps the sign-off score out of the
trial reward.

After the lift table, `lift.py` prints two scorecards:

- The pass rate per rule for each arm. A sign-off score counts only when the
  build step's verification passed.
- Per task, the skills the Consult arm read, missed, or read despite
  `expect_silent`, and each arm's sign-off mode: `stopped`, `provisional`, or
  `built`.

The judge receives the task instruction and a bundle with the git diff, new
files, and the agent's final message. `consult_lib.py prepare` writes both
into the prompt, so the `claude-code` judge scores in one turn at low effort
(`CLAUDE_CODE_EFFORT_LEVEL` in `test.sh`). It does not receive the trajectory.
Reading the trajectory with tool calls cost about 440k input tokens per trial,
and the `proof` dimension already scores the process from it. The rubric and
prompt are `verifier/shared/judge/quality.toml` and `prompt.md`.

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
  bundle, and the `prepare` step that drops the judge when it cannot run.
- `verifier/shared/consult_rules.py`: the rule checks, keyed by rule id.
- `verifier/shared/<dimension>/`: one RewardKit script per dimension.
- `verifier/hidden/<task>.mjs`: the hidden check for each code task, keyed by
  task name.
- `verifier/hidden/<task>.rules.mjs`: a runtime probe for rule checks. It
  prints `{"<rule id>": 0|1}` as its last line.
- `verifier/rules.json`: every rule of every skill, marked `check`,
  `judge-only`, or `untested`. `scripts/validate-skill-anatomy.mjs` fails when
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
4. For a code task, write `verifier/hidden/<task>.mjs` and `tests/proof/submitted.py`.
5. For a rule task, add the rule-task keys to `consult.json`. A two-step task
   also needs `steps/brief/`, `steps/approve/`, and a no-op
   `steps/brief/solution/solve.sh`, so the oracle proposes before it builds.
6. Add the name to a suite and run the sync.

Check the task with the oracle before spending model calls:

```sh
harbor run -p tasks -i <task> -a oracle -o runs --yes
```

## Known gaps

- Only `proof-first-bugfix`, the routing tasks, and the `rules` tasks have
  oracle solutions. The other code tasks run without `solution/`, so
  `-a oracle` cannot check them.
- The oracle leaves no trajectory, so trajectory-based rules such as `api.1`
  and `debugging.1` score 0 on it.
- Rule checks are heuristics until calibrated. `debugging.5` misses a fix that
  renames the source file it repairs.
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
  at `xhigh`.
- Harbor's Codex agent takes the newest session file as the trajectory and
  resumes the next step with `--last`. Both pick a subagent when Codex spawns
  one, so `agents/codex.yaml` turns `multi_agent` off. Codex's consult arm
  therefore cannot hand review to a subagent, which `code-review` prefers.
