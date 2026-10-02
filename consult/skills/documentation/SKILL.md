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
  writing skill such as [Terse](https://github.com/kreek/terse).
- Ordinary implementation where docs were not requested, approved, or
  required by a validator. Name the possible gap in the final response
  instead of editing docs.
- CHANGELOG, release notes, migration notes, version manifests; use
  `release`. API contract shape; use `api`.

## Rules

1. Documentation is a separate work product, not an implementation reflex.
   Run only when requested, approved after a concrete gap is found, or
   required by validation.
2. Check whether the answer already lives in code, schema, tests, CLI help,
   OpenAPI, or a dashboard. Write only the missing context and link the
   source of truth; do not restate generated facts.
3. Encode the rule in names, types, schemas, or tests first. Add a comment
   only for the why that remains non-obvious.
4. One doc, one reader situation (tutorial, how-to, reference, explanation,
   runbook), titled as the reader's question. Introduce terms and
   prerequisites before the step that depends on them.
5. README is purpose, install and run, minimal usage, and links onward.
6. Voice: plain, direct, concrete sentences, no em dashes, only words that
   earn their place. Split any sentence that needs rereading.
7. Delete stale docs you cannot fix now, or mark them with a tracked rewrite
   owner. Orphaned prose is misinformation.
8. Put docs next to the code or service whose reviewers can catch drift, in
   the repo's existing docs system. If none exists, choose one during
   scaffolding or with user approval.

## Tripwires

| Trigger | Do this instead | False alarm |
|---|---|---|
| "I'll update the docs while I'm here" | Ask before editing docs for an implementation change. | Docs were requested, or a validator requires the update. |
| "Restate the API details in prose" | Link the source of truth and write only the missing context. | The source is unlinkable and the fact is stable. |
| "A longer README looks more thorough" | Purpose, install/run, minimal usage, links onward. | None. |
| "Add a comment explaining this" | Encode the rule in code or tests first. | The reason cannot be expressed in code or tests. |
| "Note the release details in the README" | Route to `release`. | None. |
| "Leave the stale paragraph for now" | Delete it or mark a tracked rewrite owner. | None. |

## Handoffs

- `api`: OpenAPI and wire-contract shape.
- `observability`: alert and runbook signal definitions.
- `release`: CHANGELOG, release notes, migration notes, version manifests.
