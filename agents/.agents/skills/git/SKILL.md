---
name: git
description: "House rules for git and GitHub: committing a reviewed slice, history edits, force-push, conflicts, worktrees, and PR or issue text. Use when committing, rebasing, resolving conflicts, recovering work, force-pushing, or writing to GitHub."
---

# Git

## Iron law

Commit only the reviewed slice, staged by name. Don't rewrite shared history
or skip the recovery point.

## Rules

1. Check the tree, branch, and upstream state first, and stop on anything
   unexpected: the wrong branch, an unresolved merge, files you don't
   recognize.
2. Stage only named files for the slice, never `git add .` in a messy tree,
   and confirm the staged diff matches it. Leave unrelated changes unstaged
   and name them in the report.
3. On the default branch, create a topic branch before new work. On a topic
   branch, keep going unless the new work is unrelated; then branch off the
   default and say so. Don't ask which branch to use.
4. Before rewriting, deleting, or force-pushing, name a recovery point (a
   tag, branch, or reflog entry) and whether the branch is local, solo, or
   shared. Rewrite shared history only with explicit approval, and
   force-push with `--force-with-lease --force-if-includes`.
5. Resolve conflicts by keeping the intent of both sides, then run the
   checks. Confirm with `range-diff` or the log that the intended commits
   remain. For a generated file, resolve its source and regenerate it.
6. The host's permission system owns GitHub access; don't add a second ask
   on top of an approval the host granted. First find which GitHub tool
   exists (`gh`, a GitHub MCP server, or host tools).
7. Show PR and issue text to the user and publish only the exact text they
   approved. Never let a tool open an editor or send unreviewed text. Get
   approval before each other published write: a review comment, review
   decision, thread resolution, or push.
8. Work on a branch in the main checkout. Create a worktree only when work
   must run in parallel with uncommitted changes there; put it outside the
   repository and remove it once its work is merged.
