# Deprecation and Migration

Use this reference when release work removes, renames, replaces, sunsets, or
migrates public behavior, data, configuration, APIs, CLIs, plugins, packages,
or documented workflows.

## Rule

Compatibility paths carry maintenance cost until they have an owner and an
expiry. Deprecation must name who is affected, what replaces the old path,
when removal can happen, and how the release can recover if migration fails.
A stable public API that keeps both paths on purpose is exempt from the
expiry.

## Classification

| Kind | Meaning | Release posture |
|---|---|---|
| Advisory deprecation | Old path still works; users are encouraged to move. | Minor release with warning, migration note, and future removal version. |
| Compulsory migration | Users or data must move before old behavior can be removed. | Phased rollout with owner, deadline, tracking, rollback/recovery, and support plan. |
| Removal | Old public surface stops working or changes semantics. | Major release unless the surface was private or already outside support. |
| Internal cleanup | Private dead path removed with no caller-visible effect. | Refactor/proof path; release note only if users notice artifacts. |

## Workflow

1. Identify affected surfaces: API routes, SDK symbols, CLI flags, env keys,
   config files, database records, plugin manifests, docs, dashboards, jobs,
   webhooks, or user workflows.
2. Classify the change as advisory deprecation, compulsory migration, removal,
   or internal cleanup. When unclear, assume public until proven private.
3. Define the replacement: new API, command, config, data shape, package,
   workflow, or explicit "no replacement" rationale.
4. Plan the migration phases:
   - expand: add the new path without breaking old users;
   - notify: warnings, changelog, docs, headers, metrics, or operator notice;
   - migrate: move callers/data and track completion;
   - contract: remove the old path only after proof says it is unused.
     Proof is telemetry, search, ownership records, support policy, or the
     user's explicit confirmation. For a private path, tests and repository
     search that show it is unreachable are enough.
5. Name rollback or recovery: how to re-enable the old path, restore data,
   stop the rollout, or communicate accepted irreversibility.

## Proof Obligations

- [ ] Affected users, callers, data, and documented surfaces are listed.
- [ ] Replacement path or no-replacement rationale is explicit.
- [ ] Advisory deprecations name the future removal version or condition.
- [ ] Compulsory migrations have owner, deadline, tracking signal, and support
      path.
- [ ] Release notes or migration docs tell users what to do, not just what
      changed.
- [ ] Telemetry, search, tests, or contract checks prove whether old callers
      remain before removal.
- [ ] Rollback or recovery path is documented, or irreversibility is named and
      accepted by a human.
