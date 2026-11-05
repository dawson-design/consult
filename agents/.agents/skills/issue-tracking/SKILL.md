---
name: issue-tracking
description: "Drafts, splits, and tracks initiatives, epics, and issues sized to the team sprint and closed on evidence. Invoke with /issue-tracking when drafting or updating tracker items."
disable-model-invocation: true
---

# Issue Tracking

## Iron law

Initiative, then epic, then issue. Every issue fits in one sprint and closes
on evidence.

## Rules

1. **Three levels, at most one parent each.** An Initiative groups Epics
   toward one measured outcome. An Epic groups Issues that deliver one
   feature. Nothing goes below an Issue. A bug or chore that serves no feature
   stands alone. Never create a placeholder parent or a catch-all Epic.
2. **Map the levels onto what the tracker already has.** Read its templates,
   types, and hierarchy, use its level names, and search for duplicates and
   the right parent. Prefer native types and parent links to labels or title
   prefixes. New types, labels, fields, or hierarchy levels need the user's
   approval.
3. **Size by the team's sprint, not the agent's speed.** Read the sprint
   length from the tracker, or assume two weeks and say so. An Issue fits when
   one engineer can finish it, review included, within half a sprint, with at
   most five acceptance criteria. Otherwise split it, or file a time-boxed
   research Issue that ends in a decision. An Epic with one Issue is an Issue.
   An Epic longer than a quarter is two Epics or an Initiative.
4. **Split by behavior, not by layer or activity.** A feature Issue changes
   one behavior a user, caller, or operator can observe. A refactor or chore
   Issue names the behavior it preserves and the check that proves it. Split
   by layer only when separate teams own the layers and ask for that split.
5. **Keep Issues short, and state outcomes, not implementation.** An Issue
   body stays under 200 words, excluding code and logs, because developers
   skim longer ones. Link the Epic or Initiative instead of repeating its
   context. Criteria name observable results, not "tests written". Leave out
   steps and pseudocode. A criterion that fixes a contract stays
   proposed until the user approves it. When a criterion proves wrong
   mid-build, propose an edit instead of rewriting it.
6. **The team owns estimates, priority, sprint, assignee, and dates.** Leave
   them empty unless the user or tracker supplies them. When an owner or date is
   needed, ask or write TBD. Leave items you were not asked to
   change untouched.
7. **Write to the tracker only when the user asks for tracker work.** An Issue
   named in a task authorizes only reading it and citing it in branch, commit,
   and PR text. `git` Rule 7 covers each item's text. Get the whole
   tree approved: each item's level, title, parent, and body. After a partial
   failure, report what exists and search before retrying. With no human to
   answer, write drafts to `docs/plans/<slug>-issues.md` and publish nothing.
8. **Keep private data out of tracker text.** Redact secrets, personal data,
   and internal hosts from logs. Report vulnerabilities through the project's
   private channel, never a public item.
9. **Done means evidence, not closed children.** A PR or commit closes an
   Issue only when it meets every acceptance criterion. Otherwise it
   references the Issue. Out-of-scope work becomes a drafted follow-up. An
   Epic closes when each exit criterion has evidence. An Initiative closes
   when its measure is met or its owner cancels it.
10. **Status reports link the tracker.** Report only finished work, blockers
    and causes, risks, scope changes, decisions needed, and Initiative
    measures.

## References

- `references/templates.md`: load when drafting an item or splitting work.
- `references/github.md`: load for GitHub's issue levels, fields, commands,
  and commit keywords.
