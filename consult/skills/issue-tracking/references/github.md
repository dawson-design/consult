# GitHub Issues and Projects

Load this reference when the tracker is GitHub Issues or GitHub Projects, on
github.com or GitHub Enterprise Server (GHES).

Facts were checked against GitHub's docs, changelog, and `gh` release notes
on 2026-10-02. When a command fails, or the host's `gh` is older than
v2.94.0, recheck with `official-source-check`.

## Map the levels

| Level | GitHub shape |
|---|---|
| Initiative | An issue with the organization's Initiative type, or the closest existing type |
| Epic | An issue with the Epic type, or Feature when the organization has no Epic type, as a sub-issue of its Initiative |
| Issue | An issue with the Task or Bug type, or Feature when Epics have their own type, as a sub-issue of its Epic |
| Sprint | An iteration field in the team's project |

- **Issue types are per organization.** Organization owners define up to 25.
  The defaults are task, bug, and feature, and each can be edited or disabled.
  Adding Initiative or Epic types is an organization change: propose it under
  `workflow` Rule 7. With only the default types, propose an `initiative`
  label for Initiatives, as for personal repositories, and offer new types as
  a separate proposal. Read a repository's available types with
  `gh api repos/OWNER/REPO/issue-types`.
- **User-owned repositories.** GitHub documents issue types only for
  organizations. In a personal repository, propose labels such as
  `initiative` and `epic` together with sub-issue links.
- **Sub-issues.** A parent holds up to 100 sub-issues, nested up to eight
  levels. The skill uses three. A child can live in another repository. An
  issue has one parent, and moving it needs the replace-parent option. A new
  sub-issue inherits its parent's project and milestone by default.
  Cross-organization sub-issues are documented inconsistently, so keep a tree
  inside one organization.
- **Permissions.** Adding sub-issues and dependencies needs triage access.
  Without push access, the REST API silently drops `type`, labels, milestone,
  and assignees on create. Read the issue back after creating it.
- **Issue fields.** Organizations can define Priority, Effort, Start date,
  Target date, and other issue fields (GA 2026-07-02, GHES 3.23). These are
  team-owned values under Rule 6.
- **Milestones and iterations.** GitHub's docs present project iteration
  fields as the sprint mechanism. Milestones group issues in one repository
  around a due date. Use whichever the team already uses.

## Read before drafting

```sh
# Templates and forms
ls .github/ISSUE_TEMPLATE/

# Duplicates, open and closed
gh issue list --state all --search "guest checkout in:title"

# Existing Epics and one item's place in the tree
gh issue list --type Epic --state open
gh issue view 41 --json issueType,parent,subIssues,subIssuesSummary,blockedBy
```

A body passed to `gh issue create` or the API does not go through an issue
form. When the repository uses forms (`.yml` files), copy the form's fields
into the body.

Sprint length lives in the project's iteration field. `gh project field-list`
does not return iteration IDs or durations. Read them with GraphQL from
`ProjectV2IterationField.configuration.iterations`, and
`configuration.completedIterations` for past ones. Each iteration has an
`id`, `title`, `startDate`, and `duration`.

## Create the tree after approval

With `gh` v2.94.0 or later, create parents first and pass each child its
parent's number or URL:

```sh
gh issue create --title "Cut checkout abandonment" --body-file initiative.md --type Initiative
gh issue create --title "Guest checkout" --body-file epic.md --type Epic --parent 40
gh issue create --title "Let guests pay by card" --body-file issue.md --type Task --parent 41 --blocked-by 55
gh issue edit 57 --parent 41
gh issue edit 57 --add-blocked-by 55
```

Without those flags, use the API:

- **REST create.** `POST /repos/{owner}/{repo}/issues` accepts `type` (the
  type name) and `parent_issue_id` (the parent's integer `id`).
- **REST sub-issue.** `POST /repos/{owner}/{repo}/issues/{parent_number}/sub_issues`
  takes `sub_issue_id`, the child's integer `id`, not its number or node ID.
  `gh api repos/OWNER/REPO/issues/57 --jq .id` returns it. The `id` from
  `gh issue view --json id` is a GraphQL node ID and does not work here.
- **REST dependencies.** `POST .../issues/{issue_number}/dependencies/blocked_by`
  takes `issue_id`, the blocking issue's integer `id`. Each issue holds up to 50 links per
  direction.
- **GraphQL.** `createIssue` takes `issueTypeId`, `parentIssueId`, and
  `projectV2Ids`. `addSubIssue` takes the parent's `issueId` and the child's
  `subIssueId` or `subIssueUrl`. `updateIssueIssueType` and `addBlockedBy`
  cover type and dependency changes. All IDs are node IDs.

## Projects

- `gh` needs the `project` scope: `gh auth refresh -s project`.
- Add an issue with `gh project item-add <number> --owner <login> --url <issue-url>`,
  or `gh issue create --project "<project title>"`.
- From v2.97.0, `gh project item-edit <number> --owner <login> --url <issue-url> --field <name> --value <value>`
  sets one text, number, date, or single-select field per call.
- An iteration field needs `--iteration-id`. Get the ID from the GraphQL query
  above.
- Enable the hidden "Parent issue" and "Sub-issue progress" fields to see the
  tree. Table views show nested sub-issues in hierarchy view (GA 2026-03-19,
  GHES 3.21). Filter one Epic's children with `parent-issue:"OWNER/REPO#41"`.
- GitHub documents no roll-up of number fields, such as estimates, from
  sub-issues to their parent.
- A new project's built-in workflows set closed issues and merged PRs to
  Done. Sources disagree on whether moving an item to Done also closes the
  issue, so check the project's Workflows page before changing a status.

## Close and link

- Closing keywords (`close`, `closes`, `closed`, `fix`, `fixes`, `fixed`,
  `resolve`, `resolves`, `resolved`) in a PR description close the issue only
  when the PR merges into the default branch. A PR into any other branch
  ignores them.
- The same keywords in a commit message close the issue when the commit
  reaches the default branch.
- Each issue needs its own keyword. Another repository's issue takes the form
  `Fixes OWNER/REPO#100`.
- When a PR does not meet every acceptance criterion, reference the issue
  without a keyword, such as `Part of #57`.
- GitHub documents no automatic close of a parent when its sub-issues close.
  Close an Epic by its exit criteria.

## GHES versions

| Feature | GHES version |
|---|---|
| Sub-issues and issue types | 3.18 |
| Issue dependencies | 3.19 (REST) |
| Hierarchy view in projects | 3.21 |
| Organization issue fields | 3.23 |

On GHES, built-in project workflows run only after an enterprise owner
enables them in the projects policy.

## Sources

- [Adding sub-issues](https://docs.github.com/en/issues/tracking-your-work-with-issues/using-issues/adding-sub-issues)
- [REST API: sub-issues](https://docs.github.com/en/rest/issues/sub-issues)
- [Managing issue types in an organization](https://docs.github.com/en/issues/tracking-your-work-with-issues/using-issues/managing-issue-types-in-an-organization)
- [Creating issue dependencies](https://docs.github.com/en/issues/tracking-your-work-with-issues/using-issues/creating-issue-dependencies)
- [gh v2.94.0 release notes](https://github.com/cli/cli/releases/tag/v2.94.0)
- [About parent issue and sub-issue progress fields](https://docs.github.com/en/issues/planning-and-tracking-with-projects/understanding-fields/about-parent-issue-and-sub-issue-progress-fields)
- [About iteration fields](https://docs.github.com/en/issues/planning-and-tracking-with-projects/understanding-fields/about-iteration-fields)
- [Using the built-in automations](https://docs.github.com/en/issues/planning-and-tracking-with-projects/automating-your-project/using-the-built-in-automations)
- [Linking a pull request to an issue](https://docs.github.com/en/issues/tracking-your-work-with-issues/using-issues/linking-a-pull-request-to-an-issue)
- [Issue fields are generally available](https://github.blog/changelog/2026-07-02-issue-fields-are-now-generally-available/)
