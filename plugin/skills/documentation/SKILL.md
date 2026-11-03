---
name: documentation
description: "Only when asked to write or update docs for existing code: READMEs, runbooks, API docs, comments."
---

# Documentation

## Iron Law

`DOCUMENT ONLY WHAT NEEDS PROSE. KEEP DOCS NEAR THE CODE, CONTRACT, OR TEAM THAT MAINTAINS THEM.`

## When to Use

- The user asks for or approves READMEs, runbooks, tutorials, how-to guides,
  reference docs, module docs, or code comments describing code as it exists.
- Authoring or revising Consult SKILL.md files; skills are documentation for
  agents and follow the same rules.

## When NOT to Use

- Forward-looking documents: design docs, ADRs, RFCs, tech specs, PRDs,
  requirements, strategy. Consult does not cover these; use a dedicated
  writing skill such as [Terse](https://github.com/dawson-design/terse).
- Ordinary implementation where docs were not requested, approved, or
  required by a validator. Name the possible gap in the final response
  instead of editing docs.
- CHANGELOG, release notes, migration notes, version manifests; use
  `release`. API contract design; use `api`.

## Rules

1. Documentation is a separate work product, not an implementation reflex.
   Run only when requested, approved after a concrete gap is found, or
   required by validation.
2. Check whether the answer already lives in code, schema, tests, CLI help,
   OpenAPI, or a dashboard. Write only the missing context and link the
   source of truth; do not restate generated facts. Restate a fact only
   when its source cannot be linked and the fact is stable.
3. Encode the rule in names, types, schemas, or tests first. Add a comment
   only for the why that remains non-obvious.
4. README is purpose, install and run, minimal usage, and links onward.
5. Voice: plain, direct, concrete sentences, no em dashes, only words that
   earn their place. Split any sentence that needs rereading.
6. Delete stale docs you cannot fix now, or mark them with a tracked rewrite
   owner. Orphaned prose is misinformation.

## Handoffs

- `api`: OpenAPI and wire-contract design.
- `release`: CHANGELOG, release notes, migration notes, version manifests.
