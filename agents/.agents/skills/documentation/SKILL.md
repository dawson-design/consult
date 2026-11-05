---
name: documentation
description: "Writes or updates docs for existing code: READMEs, runbooks, API docs, and comments, linking the source of truth instead of restating it. Invoke with /documentation when docs are the deliverable."
disable-model-invocation: true
---

# Documentation

## Iron law

Document only what needs prose, and keep docs near the code, contract, or
team that maintains them.

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

