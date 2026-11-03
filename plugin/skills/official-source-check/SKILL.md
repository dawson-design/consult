---
name: official-source-check
description: Is a library, framework, or runtime API current, deprecated, or version-specific? Check official docs first.
---

# Official Source Check

## Iron Law

`MODEL MEMORY IS A HINT, NOT EVIDENCE, FOR VERSION-SENSITIVE BEHAVIOR.`

## When to Use

- Implementation depends on current external framework, library, runtime,
  browser, SDK, cloud, or platform behavior that the repo does not already
  prove.
- The user asks for current, official, documented, or verified
  implementation.

## When NOT to Use

- Project-local logic with tests and no external API dependency.
- Stable language syntax covered by the compiler, linter, or type checker.
- Emergency mitigation where the user accepts unverified risk.

## Rules

1. Find the local version first: manifests, lockfiles, imports, generated
   clients, schemas, config, CI images. Report its absence if none exists.
2. Check the narrow source of truth for the exact pattern: official docs,
   release notes, migration guide, standards spec, or provider SDK
   reference. Official sources beat blog posts.
3. Surface conflicts between source guidance and local convention. Use the
   smallest source-compatible implementation.
4. When source guidance alone does not prove runtime behavior, prove it with
   `proof`.
5. In the final report, name the source checked, or mark the statement
   unverified and say where you looked.

## Handoffs

- `proof`: runtime evidence behind source guidance.
- `documentation`: capture the checked source for maintainers when asked.
