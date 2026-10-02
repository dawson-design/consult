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
3. Each behavior-preservation claim gets a Proof Contract: unchanged
   behavior, invariant, public boundary, before/after check, evidence. Add
   characterization tests where coverage is missing. An unproven refactor is
   reported as unproven.
4. For public interfaces, use parallel change: expand, migrate callers,
   contract. Ask which callers, data, and releases must keep working before
   adding shims, dual paths, or migration machinery.
5. Delete old paths only when verification proves callers and traffic have
   moved. Leftover migration or deletion work has an owner and a deadline.
6. For broad renames, write a rename map first, separating private symbols,
   file paths, runtime and public keys, persisted names, docs, and
   compatibility cleanup.
7. Shorter is simpler only when it hides no state, effect, compatibility,
   ownership, or independent behavior. Simplification removes complexity with
   a named cost: hidden mutable state, unnecessary layer, broad helper,
   scattered behavior, compatibility shim, dead flag, duplicated rule with
   divergent meaning.
8. Deleted tests are replaced by equal or stronger behavior coverage.
9. No big-bang rewrites. Take the next safe slice or a branch-by-abstraction
   path; the system is shippable at every commit.

## Tripwires

| Trigger | Do this instead | False alarm |
|---|---|---|
| "It's just a refactor, no tests needed" | Name the preservation proof; add characterization where coverage is missing. | A mechanical rename the tooling already verifies. |
| "Fix the behavior while I'm in here" | Split structural and behavioral changes before committing. | None. |
| "Extract a helper to shorten this" | Name the behavior, state, effect, or boundary being separated first. | The coupling is already named. |
| "Shorter code is simpler" | Check what the shorter version hides before keeping it. | None. |
| "Nobody uses the old path anymore" | Prove no callers remain, or use expand-contract. | Verification already proves traffic and callers have moved. |
| "A rewrite would be faster" | Take the next safe slice or branch by abstraction. | The scope is small, disposable, and the user approved a rewrite. |

## Handoffs

- `proof`: preservation evidence, characterization, boundary tests.
- `commit`: grouping structural and behavioral commits.
- `domain-modeling`: effects or domain shape.
- `architecture`: module boundaries, locality, layering.
- `workflow` `references/simple-not-easy.md`: real coupling vs local ease.
