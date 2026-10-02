---
name: release
description: Only when asked to prepare a release, or when a project check requires release file sync.
---

# Release

## Iron Law

`BREAKING CHANGES BUMP MAJOR. AGENTS PREPARE RELEASES; HUMANS MUTATE SHARED ENVIRONMENTS.`

## When to Use

- The user asks for release prep, versioning, changelog, release notes,
  tags, publish planning, rollout, rollback, deprecation, or migration notes.
- The user approves release prep after a concrete diff exposes release
  artifacts or rollout obligations.
- A repo validator requires release artifact sync for an approved change.

## When NOT to Use

- Starting release work because a change might later need it. Note the risk
  in `workflow` and ask at the concrete release-prep decision point.
- Triggering deploys, rollbacks, promotions, production config, flag flips,
  DNS, or infrastructure applies. Prepare the command or checklist for a
  human.
- Database DDL safety; pair with `database`. Local bootstrap; use
  `scaffolding`.

## Rules

1. Release is a late gate. Implementation approval is not release approval.
2. Agents prepare evidence, notes, checks, runbooks, and command plans.
   Humans run anything that mutates a shared environment, including staging
   config and feature flags. Report agent-run checks and human-run commands
   separately.
3. Classify per release unit. In a monorepo, each library, CLI, plugin
   manifest, or container may have its own stream; lockstep bumps need repo
   policy or user approval. Use the higher plausible bump when compatibility
   is unclear.
4. Release artifacts move together: manifests, committed lockfile, CHANGELOG
   entry, tag plan, dependency ranges, package metadata, publish order.
   Validate dependency resolution, dry-run packaging, and registry state
   before any tag plan.
5. Ask before keeping lockfile or package-manager changes produced by a
   validation run.
6. Prove a release script's scope matches the selected release units before
   trusting it to bump artifacts.
7. Rollback must be faster than fix-forward and covers data, caches, config,
   and external side effects, not only code. Keep canary or progressive gates
   or name the equivalent.
8. Feature flags default off and carry an owner, expiry, cleanup work, and a
   human-owned production change path. Kill-switches for existing behavior
   are the exception.

## Workflow

1. Confirm the gate (Rule 1) and the scope: docs-only notes, version and
   changelog edits, packaging checks, rollout planning, or human-run steps.
2. Map release units from manifests, lockfiles, workspace config, release
   scripts, changelog, tags, and registry state.
3. Classify impact and choose the target version per unit.
4. Edit the approved artifacts together, validate, then plan rollout and
   rollback with named artifact, environment, operator, and gates. For
   deprecation or removal, load `references/deprecation-and-migration.md`.

## Tripwires

| Trigger | Do this instead | False alarm |
|---|---|---|
| "This might need a release, start release work" | Load `release` only at an explicit release-prep decision. | The user asked for release prep. |
| "I can run the deploy/rollback myself" | Prepare it for a human operator. | The user directed the agent to run that command against a non-shared environment. |
| "The release script knows what to bump" | Prove the script's scope matches the selected release units first. | The script's scope is already proven for these units. |
| "Keep whatever the validation run changed" | Ask before keeping lockfile or package-manager changes. | The user requested those exact changes. |
| "The manifest is updated, we're done" | Check lockfiles, bundled dependencies, plugin metadata, tarball contents, and publish order. | None. |
| "Reverting the code is rollback enough" | Name rollback for data, caches, config, and external side effects. | The release touches none of those. |
| "Default the new flag on" | Default off, with owner, expiry, and cleanup. | The flag is a kill-switch for existing behavior. |

## Handoffs

- `api`: HTTP compatibility, `Sunset` and `Deprecation` headers.
- `database`: migration mechanics and production data safety.
- `observability`: rollout metrics, dashboards, alerts, runbooks.
- `security`: CI credentials, artifact signing, dependency trust.
- `git-workflow`: clean version and release commits.
- `documentation`: migration guides and reference docs.

## References

- `references/deprecation-and-migration.md`: load for deprecation, removal,
  or sunset work.
