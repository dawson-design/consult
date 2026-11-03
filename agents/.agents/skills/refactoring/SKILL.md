---
name: refactoring
description: Restructuring or untangling code without changing behavior, or before extending tangled code. Load before editing.
---

# Refactoring

## Iron Law

`GREEN BEFORE THE REFACTOR. GREEN AFTER EACH STEP. NEVER MIX STRUCTURE AND BEHAVIOR IN ONE COMMIT.`

## When to Use

- Changing structure while preserving behavior: legacy refactors, large
  renames, extractions, migrations, branch by abstraction, strangler fig,
  characterization tests, big-bang rewrite avoidance.

## When NOT to Use

- Behavior-first feature work; use `proof`.
- Commit grouping or history surgery after changes exist; use `commit` or
  `git-workflow`.

## Rules

1. Every commit is structural or behavioral, never both. Opportunistic
   tweaks and behavior fixes go in separate behavior commits or are left out.
2. Name the coupling being separated (data shape, side effect, module
   boundary, ownership, time, transport, persistence, compatibility) before
   code moves. "Extract a helper to shorten this" is not a named coupling.
   Name the proof that behavior is preserved, and add characterization tests
   where coverage is missing; a mechanical rename the tooling verifies needs
   no characterization tests.
3. For public interfaces, use parallel change: expand, migrate callers,
   contract. Settle which callers, data, and releases must keep working
   (core rule 6) before adding shims, dual paths, or migration machinery.
   Contract only after evidence proves no callers remain: search, telemetry,
   ownership records, or the owner's confirmation.
4. Shorter is simpler only when it hides no state, effect, compatibility,
   ownership, or independent behavior. Simplification removes complexity with
   a named cost: hidden mutable state, unnecessary layer, broad helper,
   scattered behavior, compatibility shim, dead flag, duplicated rule with
   divergent meaning.
5. No big-bang rewrites. Take the next safe slice or a branch-by-abstraction
   path; the system is shippable at every commit. A small, disposable scope
   may be rewritten when the user approves the rewrite.

## Handoffs

- `proof`: preservation evidence, characterization, boundary tests.
- `commit`: grouping structural and behavioral commits.
- `domain-modeling`: effects or domain shape.
- `architecture`: module boundaries, locality, layering.
