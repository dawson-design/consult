---
name: release
description: "Prepares a release: version bumps per release unit, changelog, artifacts that move together, rollout and rollback plans, and feature flags. Invoke with /release when preparing a release."
disable-model-invocation: true
---

# Release

## Iron law

Breaking changes bump major. Agents prepare releases; humans change shared
environments.

## Rules

1. Release is a late gate. Implementation approval is not release approval.
2. Agents prepare evidence, notes, checks, runbooks, and command plans.
   Humans run anything that mutates a shared environment, including staging
   config and feature flags. Report agent-run checks and human-run commands
   separately.
3. Classify per release unit. In a monorepo, each library, CLI, plugin
   manifest, or container may have its own stream; lockstep bumps need repo
   policy or user approval. Use the higher plausible bump when compatibility
   is unclear. Treat a surface as public until proven private. A user-facing
   deprecation or removal names the replacement (or why there is none), the
   removal version or condition, and migration steps.
4. Release artifacts move together: manifests, committed lockfile, CHANGELOG
   entry, tag plan, dependency ranges, package metadata, publish order.
   Validate dependency resolution, dry-run packaging, and registry state
   before any tag plan. Check bundled dependencies and the packed tarball
   contents, not only the manifest.
5. Ask before keeping lockfile or package-manager changes produced by a
   validation run.
6. Prove a release script's scope matches the selected release units before
   trusting it to bump artifacts.
7. Rollback must be faster than fix-forward and covers data, caches, config,
   and external side effects, not only code. Keep canary or progressive gates
   or name the equivalent. Where a step cannot be rolled back, name it and
   get explicit human acceptance.
8. Feature flags default off and carry an owner, expiry, cleanup work, and a
   human-owned production change path. Kill-switches for existing behavior
   are the exception. Compatibility paths (aliases, shims, deprecated
   surfaces) also carry an owner and a removal condition, unless both paths
   are intentionally supported.

