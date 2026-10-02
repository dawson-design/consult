---
name: commit
description: "Only when asked to commit: staging, splitting commits, commit messages."
---

# Commit

## Iron Law

`COMMIT ONLY THE REVIEWED SLICE. STAGE FILES BY NAME.`

The host owns git invocation; this skill sets the packaging standard.

## When to Use

- The user asks to commit, stage, split, or package current changes.
- Dirty files need grouping into logical commits, or a commit needs a
  subject and body.

## When NOT to Use

- Branches, conflicts, rebases, recovery, force-push, GitHub; use
  `git-workflow`.
- Reviewing the diff; use `code-review` first for non-trivial work.
- Versions, changelogs, tags, publishing; use `release` when approved.

## Rules

1. Check the tree state first and stop on anything unexpected: wrong branch,
   unresolved merge state, files you do not recognize.
2. A branch is not the commit boundary. Group changes by behavior so one
   behavior can be reverted without dragging unrelated work. Nearby work that
   would need a different rollback decision waits for its own commit.
3. Stage only named files or approved pathspecs for the reviewed slice. Never
   `git add .` in a messy tree. Confirm the staged diff matches the slice.
   Unrelated dirty or untracked files stay unstaged and are named as
   deferred.
4. Confirm the relevant proof is current before committing. If a broad suite
   is noisy for unrelated reasons, name the targeted proof and report the
   drift separately.
5. The subject completes "When applied, this commit will ...". Add a body
   only when the change needs context, at most 2-3 short paragraphs.
6. Attribution trailers are host configuration, not message content. When a
   host adds `Co-Authored-By` or similar by default, point the user at the
   setting that disables it (`includeCoAuthoredBy: false` in Claude Code)
   rather than overriding the host from inside the message.
7. Never skip hooks. Run the hook, or fix and report its blocker.

## Tripwires

| Trigger | Do this instead | False alarm |
|---|---|---|
| "git add . is faster" | Stage named files or approved pathspecs only. | Fresh scaffold with a clean tree where every file belongs. |
| "Commit everything dirty" | Separate reviewed work from unrelated files first. | The user explicitly approved the full dirty tree. |
| "Skip hooks to save time" | Run the hook or fix and report its blocker. | None. |
| "Add Co-Authored-By or AI attribution" | Suggest the host setting that disables generated trailers, such as `includeCoAuthoredBy: false` in Claude Code. | The user explicitly requested a specific trailer. |

## Handoffs

- `git-workflow`: branches, conflicts, rebases, recovery, GitHub.
- `code-review`: before committing non-trivial implementation changes.
- `proof`: when the evidence for the staged behavior is unclear.
- `release`: approved version, changelog, tag, or publish work.
