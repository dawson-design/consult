---
name: git-workflow
description: Use for branches, history edits, conflicts, rebases, recovery, force-push, gh.
---

# Git Workflow

## Iron Law

`NEVER REWRITE SHARED HISTORY OR SKIP RECOVERY.`

The host owns git mechanics and access permission. This skill owns the
gates: recoverability and approval of published text.

## When to Use

- Rebases, merge conflicts, bisects, reflog recovery, branch cleanup, PR
  history repair, force-push decisions, or any GitHub access.

## When NOT to Use

- Staging, splitting, or committing reviewed work; use `commit`.
- Issue hierarchy, sizing, and tracker fields; use `issue-tracking`.
- Reviewing correctness; use `code-review`. Refactor planning; use
  `refactoring`. CI failure triage; use `debugging`.

## Rules

1. Branch without ceremony. Starting new work on the default branch, create
   a topic branch first. On an existing topic branch, keep going unless the
   new work is clearly unrelated; then branch off `main` and say which branch
   received the work. Do not ask which branch to use.
2. The host's permission system owns GitHub access. Hosts already gate network
   calls and `gh` under the user's account, so do not add a second chat-level
   ask on top of an approval the host granted. Reserve your own questions for
   writes that publish user-owned text and for destructive operations.
   Identify the surface first (`gh` CLI, GitHub MCP, or host tools); `gh` is
   absent from some sandboxes, which does not mean GitHub is out of reach.
3. Humans approve PR and issue text before it is published. Draft the title
   and body locally, show them, and get approval of that exact text. Never
   let a tool open an editor or send unreviewed text.
4. Inspect tree, branch, and upstream state before any history operation, and
   stop on unexpected state. Name a recovery point (tag, branch, or reflog
   entry) and whether the branch is local, solo, or shared before rewriting,
   deleting, or force-pushing. Shared history is rewritten only with explicit
   approval; force pushes use `--force-with-lease --force-if-includes`.
5. Resolve conflicts by preserving intent from both sides, then run the
   relevant checks. Verify with `range-diff` or log inspection that intended
   commits remain.
6. Test hook policy, not hook wrappers. A hook that only execs a repo script
   needs no test; the script that selects commands, blocks branches, or
   routes files does.
7. This skill never bypasses the host's sandbox or approval gates.

## Tripwires

| Trigger | Do this instead | False alarm |
|---|---|---|
| "Force push should fix it" | Verify the branch is local/solo or approved, then use lease and inclusion protection. | Disposable local-only branch with no remote. |
| "Rewrite this shared branch" | Stop and ask for explicit approval plus a recovery point. | The branch is confirmed local and unpublished. |
| "Resolve conflict by taking ours/theirs" | Preserve intent from both sides, then run checks. | A generated file regenerated after the source conflict is resolved. |
| "The host approved `gh` once, so publish freely" | Host permission covers access; publishing user-owned text still needs the user's approval of that text. | The user already approved that exact text and operation. |
| "`gh` isn't installed, so GitHub is out of reach" | Check for a GitHub MCP server or host tools and go through the host's permission flow. | The host exposes no GitHub surface. |
| "Just open the PR with a quick title" | Draft title and body, get approval, then create it. | The user already approved that exact title and body. |

## Handoffs

- `commit`: staging, splitting, and committing approved work.
- `refactoring`: separating structural and behavioral changes in code.
- `release`: version bumps, CHANGELOG entries, tags in the working tree.
- `debugging`: reproduce before bisecting.
- `issue-tracking`: issue hierarchy, sizing, and tracker fields.
