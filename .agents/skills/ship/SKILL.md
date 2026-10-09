---
name: ship
description: Run Consult's guarded maintainer flow for commit, merge, version bump, validation, and push.
---

# Ship

## When to Use

- Use when the user asks to ship this Consult repository or explicitly invokes
  `$ship`.
- Use only for this repository's maintainer release flow: commit, merge to
  `main`, bump release artifacts, validate, and push.

## When NOT to Use

- Do not use for ordinary commits; use the `commit` skill instead.
- Do not use for release preparation by itself; use the `release` skill.
- Do not use outside this repository.

## Iron Law

`DO NOT RUN THE WHOLE SHIP FLOW UNATTENDED; STOP AT EVERY CONFIRMATION GATE.`

## Repo Facts

- Main branch is `main`; remote is `origin`.
- Plugin version lives in `plugin/.claude-plugin/plugin.json`,
  `plugin/.codex-plugin/plugin.json`, `plugin/.cursor-plugin/plugin.json`,
  `.claude-plugin/marketplace.json`, and `.cursor-plugin/marketplace.json`.
  `plugin/plugin.json` should match these too; reconcile drift when bumping.
- Root `package.json` is private tooling and is not versioned for release.
- Version marker is the `CHANGELOG.md` header `## [X.Y.Z] (YYYY-MM-DD)`.
  Promote `## [Unreleased]` into a dated version section and leave a fresh
  empty `## [Unreleased]` above it.
- Releases are not git-tagged in this repo. Do not create or push a tag unless
  the user explicitly asks.
- Commit messages use imperative subjects and no author-attribution trailers.

## Workflow

1. Pre-flight: run `git status` and `git rev-parse --abbrev-ref HEAD`. If the
   working tree is clean and already on `main`, report that there is nothing to
   ship and stop.
2. Commit: review `git diff` and `git diff --cached`, group uncommitted changes
   into logical commits, propose the grouping, and get user approval before
   committing on the current branch.
3. Merge to main, only when not already on `main`: run `git fetch origin`, bring
   `main` up to date, get user approval, then merge the current branch into
   `main`. On conflicts, stop and show the conflicted files.
4. Bump the version on `main`: use the `release` skill to classify the bump from
   the merged diff, or use the user's explicit `patch`, `minor`, or `major`
   override. Confirm the proposed version before writing. Update the relevant
   release artifacts and commit the bump as `Release <version>`.
5. Validate and push: run the project validation gate before pushing. Abort on
   failure. Get user approval before `git push origin main`.

## Before Saying Done

Report the branch shipped, merge result, old and new version, validation
result, pushed commit, and any remaining plugin-sync work.

## Verification

- [ ] The skill stopped at each approval gate before committing, merging,
      versioning, and pushing.
- [ ] The version bump matched the actual changed surface.
- [ ] `CHANGELOG.md` and every relevant manifest agreed after the version bump.
- [ ] Validation ran before push, or the skipped validation is clearly reported.
