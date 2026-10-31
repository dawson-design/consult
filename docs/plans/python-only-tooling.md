# Plan: Python-only maintainer tooling

Status: approved 2026-10-31 with the recommended option for every decision.
Steps 0 to 2 are built now. Steps 3 onward wait until
`refactor/always-on-core` merges, then this branch rebases onto `main` and
ports the merged JS.
Branch to build on: `refactor/python-only-tooling`, cut from `main`.

## Intent

Consult's maintainer tooling is split between Node (`scripts/*.mjs`, Vitest
tests, pnpm, remark) and Python (`eval/`, a `uv` project). Neither side has a
linter or formatter. Move all repo-owned tooling code to Python, add one
linter and formatter (ruff) over all of it, and remove pnpm, Vitest, and
`package.json` from the repo.

This is a clean cutover. Old commands (`node scripts/*.mjs`, `pnpm test`,
`pnpm run check:links`) stop working in the same PR and nothing replaces them
under the old names. The maintainer is the only person who runs them.

Plugin users are not affected: nothing under `plugin/` changes, and no skill
text changes.

## What stays JavaScript, and why

These files are eval task content, not tooling, and stay as they are:

- `eval/verifier/hidden/*.mjs` and their vendored copies in
  `eval/tasks/*/tests/`: hidden checks that run against JS workspaces written
  by the agent under test.
- `eval/tasks/*/environment/workspace/**`, `eval/triggers/fixtures/**`,
  `eval/verifier/tests/fixtures/**`: task and test fixtures.

Node stays a runtime dependency of the eval suite only:
`eval/verifier/tests/test_hidden_checks.py` runs the hidden checks with
`node --input-type=module -e` and needs Node 22. CI keeps
`actions/setup-node` for that step alone.

## Acceptance criteria

1. No tracked JS/TS tooling files remain outside the eval content listed
   above:
   `git ls-files '*.mjs' '*.js' '*.cjs' '*.ts' ':!eval/tasks' ':!eval/verifier/hidden' ':!eval/verifier/tests/fixtures' ':!eval/triggers'`
   prints nothing.
2. `package.json`, `pnpm-lock.yaml`, and `pnpm-workspace.yaml` are deleted.
3. `git grep -nE 'pnpm (test|run|install)|vitest|node scripts/'` matches
   nothing outside `CHANGELOG.md` history, skill content under
   `agents/.agents/skills/` and `plugin/skills/`, and eval fixtures.
4. The Python anatomy validator produces byte-identical stdout and the same
   exit code as the JS validator on every golden scenario (see Proof).
5. `ruff check` and `ruff format --check` pass over `scripts/`, `tests/`, and
   `eval/` (excluding vendored copies and fixtures). `make test`, the
   pre-commit hook (when `.py` files are staged), and CI all run them.
6. `make test` passes on a machine with only `python3` 3.12+, `uv`, `git`,
   and the link checker installed: no Node, no pnpm.
7. CI runs the same checks as today plus lint, with zero skipped tests.
8. `./setup.sh` still regenerates `plugin/skills/` (now through `python3`).

## Constraints

- Behavior-preserving port. Each validator finding, message, and exit code
  stays the same. The only output that may change is usage text that names
  the command. No new checks are added to the validator or generator in this
  work.
- Stdlib only for `scripts/` and `tests/`, so `python3 scripts/...` runs with
  no install, matching how CI already runs `eval/scripts/sync_tests.py`.
  ruff is the only Python dev dependency.
- Tests use `unittest`, matching `eval/verifier/tests`.
- Python 3.12 minimum, matching `eval/pyproject.toml`.
- Each commit is either structural or behavioral, and the tree stays green
  after each one.
- The approved always-on-core plan (`refactor/always-on-core`) generates
  `plugin/hooks/hooks.json` from `workflow/references/core.md` and changes
  the validator's hook check. Both the generator and the validator are files
  this plan ports, so do not build the two in parallel (Decision 5).
- `main` is protected and needs the CI job named `checks` to pass. Keep that
  job name. Land through a PR merged with a merge commit.
- No push without the maintainer's go-ahead. CI runs on the existing
  `ubuntu-latest` workflow with unchanged triggers, so no new paid service
  is involved.

## Rename map

| Old | New |
| --- | --- |
| `scripts/generate-plugin-symlinks.mjs` | `scripts/generate_plugin_symlinks.py` (keeps `MIRROR_DESTS`) |
| `scripts/validate-skill-anatomy.mjs` | `scripts/validate_skill_anatomy.py` (keeps `--self-test`) |
| `scripts/pre-commit-acceptance.mjs` | `scripts/pre_commit_acceptance.py` |
| `scripts/validate-markdown-links.mjs` + remark | lychee, or `scripts/check_markdown_links.py` (Decision 2) |
| `tests/helpers.mjs` | `tests/helpers.py` |
| `tests/<name>.test.mjs` | `tests/test_<name_with_underscores>.py` |
| `pnpm test` | `python3 -m unittest discover -s tests` |
| `pnpm run check:links` | `make links` |
| `pnpm install` | `uv sync` (root dev group: ruff) |
| `node scripts/validate-skill-anatomy.mjs` | `python3 scripts/validate_skill_anatomy.py` |
| `node scripts/generate-plugin-symlinks.mjs` | `python3 scripts/generate_plugin_symlinks.py` |
| `exec node scripts/pre-commit-acceptance.mjs` | `exec python3 scripts/pre_commit_acceptance.py` |
| new | `make lint` (ruff check + format check) |

Script names use underscores because the validator and tests import from
the generator (`MIRROR_DESTS`).

## Decisions to approve

1. **ruff configuration.** Root `pyproject.toml` (uv, `package = false`,
   dev group `ruff` pinned to an exact version, `uv.lock` committed) and
   `.python-version` = `3.12`. ruff's default rule set, `line-length = 120`.
   Exclude `eval/tasks/` (vendored copies, regenerated by `sync_tests.py`)
   and all fixture directories. Baseline on `eval/` with ruff 0.17.2: 107
   lint findings (74 with safe automatic fixes), and 30 files would be
   reformatted. The reformat lands as one formatting-only commit.
2. **Link checker.** remark-validate-links checks local file links and
   heading anchors. Recommendation: spike lychee
   (`lychee --offline --include-fragments`) first. lychee is a new dependency
   (`brew install lychee` locally, `lycheeverse/lychee-action` in CI), and its
   docs do not confirm that it matches local Markdown heading anchors, so the
   spike has to prove it. If the spike fails any criterion in step 6, write
   `scripts/check_markdown_links.py` in stdlib Python instead.
3. **Pre-commit hook gains ruff.** When `.py` files are staged, the hook runs
   `uv run ruff check` and `uv run ruff format --check`, and skips with a
   message when `uv` is missing, the same way it handles a missing `pnpm`
   today. This is the only behavior change to existing tooling, and it gets
   its own commit.
4. **Keep `--self-test`.** It overlaps with the unittest suite, but removing
   it would change behavior inside a port. Revisit separately if wanted.
5. **Order against always-on-core.** Recommendation: merge always-on-core
   first, then start this plan from the new `main`. That plan was approved
   first and is small, and porting afterward means the generated-hook logic
   is ported once, in Python, instead of being written in JS and then
   rewritten. Steps 1 and 2 (ruff over `eval/`, tests pointed at the JS
   scripts) can start right away.

## Rebase onto always-on-core (before step 3)

Steps 0 to 2 were built from `main` at `c5595a9`. always-on-core changes
three Vitest files that step 2 already ported:
`tests/generate-plugin-symlinks.test.mjs`, `tests/plugin-session-hook.test.mjs`,
and `tests/validate-skill-anatomy.test.mjs`. After rebasing onto `main`:

1. Port the cases those files gained or changed into
   `tests/test_generate_plugin_symlinks.py`, `tests/test_plugin_session_hook.py`,
   and `tests/test_validate_skill_anatomy.py`
   (`git diff c5595a9 main -- tests/*.test.mjs` lists them).
2. Re-run `uv run ruff format` and `python3 eval/scripts/sync_tests.py` if
   always-on-core touched `eval/` Python, then `make test`.
3. Continue with step 3.

An approving design or RFC approves the direction, not the concrete shapes.
Sign-off on this plan covers the rename map and the decisions above. Nothing
else in the work is a durable shape.

## Ordered steps

Each step ends with the narrowest check listed, then `make test` before
committing.

0. **Branch and plan.** Cut `refactor/python-only-tooling` from `main` and
   commit this file.
1. **ruff over existing Python.**
   - 1a: add root `pyproject.toml`, `.python-version`, `uv.lock`, ruff config,
     `.venv/` in `.gitignore`, and a `make lint` target. Lint is not yet
     required to pass.
   - 1b: `ruff format` over `eval/`, then `python3 eval/scripts/sync_tests.py`
     to refresh vendored copies. Formatting only.
   - 1c: fix the lint findings. Apply ruff's safe automatic fixes, then fix
     the rest by hand without changing behavior (for example
     `check=False` where `subprocess.run` relied on the default). `make test`
     now runs `make lint`, and CI gains a lint step (`astral-sh/setup-uv`,
     pinned).
   - Check: `python3 eval/scripts/sync_tests.py --check`,
     `python3 -m unittest discover eval/verifier/tests`, `make lint`.
2. **Port the tests first, pointed at the JS scripts.** Write
   `tests/helpers.py` and a `test_*.py` for every Vitest file, with the same
   cases. Each CLI test module names its command in one constant (for
   example `COMMAND = ["node", "scripts/validate-skill-anatomy.mjs"]`).
   `test_setup_sh.py`, `test_update_installed_plugins.py`, and
   `test_plugin_session_hook.py` test Bash and JSON, so they are finished at
   this step. Keep `skipUnless(shutil.which("expect"))` on the confirmation
   tests, and keep `PATH=/usr/bin:/bin` for the missing-stow test.
   - `make test` and CI run both suites until step 7.
   - Check: the unittest suite and Vitest both pass against the JS scripts.
     For each ported file, break the script under test on purpose and
     confirm the suite goes red.
3. **Port the generator.** Write `scripts/generate_plugin_symlinks.py`, flip
   `COMMAND` in its test, and switch `setup.sh` (lines 190 and 416 to 422)
   from `node` to `python3`. Delete the `.mjs` file and its Vitest test.
   - In `test_generate_plugin_symlinks.py`, replace the local `MIRROR_DESTS`
     with the generator's and assert it equals `["plugin/skills"]`, restoring
     the Vitest guard against a dropped mirror destination.
   - Check: `test_generate_plugin_symlinks.py`; run `./setup.sh` and confirm
     `git status` shows no drift in `plugin/skills/`.
4. **Port the anatomy validator.** Write `scripts/validate_skill_anatomy.py`,
   importing `MIRROR_DESTS` from the generator. Port faithfully, splitting
   functions over about 30 lines only where the split is mechanical. Run the
   golden comparison (Proof, P2) before flipping `COMMAND`. Delete the `.mjs`
   file and its Vitest test.
   - Check: `test_validate_skill_anatomy.py`, `--self-test`, golden diff.
5. **Port the pre-commit script.** Write `scripts/pre_commit_acceptance.py`
   and update `.githooks/pre-commit`. The link-check entry keeps calling the
   current checker until step 6. Delete the `.mjs` file and its Vitest test.
   Then, as a separate commit, add the ruff checks (Decision 3).
   - Check: `test_pre_commit_acceptance.py`; stage a `.py` file with a lint
     error on a scratch branch and confirm the hook blocks it.
6. **Replace the link checker.** Spike criteria for lychee, run on a scratch
   copy: it must (a) flag a broken relative file link, (b) flag a missing
   heading anchor in another file, (c) flag a missing same-file anchor,
   (d) pass the current tree with no false positives (code blocks, reference
   links, HTML anchors), and (e) make no network calls. If any fails, use the
   stdlib Python fallback with unittest fixtures for (a) to (d). Add
   `make links`, and point the pre-commit check and CI at it.
   - Check: the four seeded failures go red and the clean tree goes green.
7. **Remove Node tooling.** Delete `package.json`, `pnpm-lock.yaml`,
   `pnpm-workspace.yaml`, `scripts/validate-markdown-links.mjs`, and
   `tests/helpers.mjs`. In CI, drop `pnpm/action-setup`, the pnpm cache, and
   `pnpm install`; keep `setup-node` (Node 22) with a comment saying it serves
   only `test_hidden_checks.py`; change the skip assertion to match
   unittest's `skipped=` output. Keep `node_modules/` in `.gitignore`, since
   eval fixtures can create it.
   - Check: acceptance criteria 1 to 3 by command; `make test` with `node`
     removed from `PATH`.
8. **Docs.** Update every command reference from the rename map:
   `AGENTS.md` (Common commands, Validation scope, Conventions: "Markdown and
   Python are the repo-owned languages; JS appears only as eval content"),
   `CONTRIBUTING.md` (lines 14 and 88 to 89), `eval/README.md` (line 370),
   the `ci.yml` comment (line 17), `.agents/skills/ship/SKILL.md` (line 32:
   root `pyproject.toml`, not `package.json`, is unversioned tooling), and a
   `CHANGELOG.md` `## [Unreleased]` entry. Make no version bump; `ship`
   classifies it at release time.
   - Check: acceptance criterion 3, `make links`,
     `python3 scripts/validate_skill_anatomy.py`.
9. **Review.** Run a fresh-context code review with this plan's intent,
   acceptance criteria, constraints, proof evidence, and the branch diff. Fix
   the findings and repeat until the review is clean. Then rebase onto
   `main`. With the maintainer's go-ahead, push and open a PR with
   approved text, wait for `checks`, and merge with a merge commit.

## Proof

| ID | Claim | Boundary | Check | Evidence to record |
| --- | --- | --- | --- | --- |
| P1 | The ported tests specify the same behavior as the Vitest tests | CLI of each JS script | unittest suite green against the JS scripts, plus one deliberate red per file | Test names, the red/green output |
| P2 | The Python validator matches the JS validator | `validate_skill_anatomy` CLI stdout, stderr, exit code | Golden diff: run both on (a) the real repo, (b) every fixture tree the validator tests build, (c) a repo copy seeded with one violation per finding type (description length, total description budget, word budget, tripwire rows and header, obsolete sections, model key, em dash, approval sentence, attribution, routing table, mirror drift, each manifest check, hook check, rule coverage). Expect no diff except usage text. | `diff` output (empty) for every scenario |
| P3 | The generator is unchanged | Files written under `plugin/skills/` | `test_generate_plugin_symlinks.py`; `./setup.sh` then `git status` | Clean status |
| P4 | Pre-commit selection is unchanged, and ruff blocks a bad `.py` file | Hook exit code | `test_pre_commit_acceptance.py`; scratch-branch commit attempt | Hook output |
| P5 | The new link checker is at least as strict as remark | `make links` exit code | Step 6 seeded failures (a) to (d) | Red for each seed, green for the clean tree |
| P6 | Node is no longer needed outside eval | `make test` | `env PATH=<PATH without node> make test` | Green run |
| P7 | Old paths are gone | Repo tree | Acceptance criteria 1 to 3 commands | Empty output |
| P8 | CI is equivalent and nothing skips | GitHub Actions run | First CI run on the pushed branch | Run link, `skipped=` absent |

## Out of scope

- A Python type checker (mypy or pyright). Add one later if wanted; ruff
  catches syntax errors, which meets the minimum bar.
- New validator checks, or removing `--self-test`.
- Changes to eval task content or the hidden `.mjs` checks.
- Deleting the untracked `packages/pi-core` and `packages/pi-proof`
  directories (each holds only `node_modules`). They are local leftovers,
  not tracked files; remove them by hand if wanted.
