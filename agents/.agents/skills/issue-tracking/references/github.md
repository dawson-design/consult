# GitHub Issues and Projects

Facts were checked against GitHub's docs, changelog, and `gh` release notes
on 2026-10-02. When a command fails, or the host's `gh` is older than
v2.94.0, recheck the official docs.

## Map the levels

| Level | GitHub shape |
|---|---|
| Initiative | An issue with the organization's Initiative type, or an `initiative` label when the organization has only the default types |
| Epic | An issue with the Epic type, or Feature when the organization has no Epic type, as a sub-issue of its Initiative |
| Issue | An issue with the Task or Bug type, or Feature when Epics have their own type, as a sub-issue of its Epic |
| Sprint | An iteration field in the team's project, or a milestone when the team plans sprints with milestones |

- **Issue types are per organization.** Read a repository's available types
  with `gh api repos/OWNER/REPO/issue-types`. Personal repositories have no
  issue types, so propose `initiative` and `epic` labels with sub-issue
  links.
- **Sub-issues.** An issue has one parent, and moving it needs the
  replace-parent option. A new sub-issue inherits its parent's project and
  milestone by default. A child can live in another repository, but keep a
  tree inside one organization, because cross-organization sub-issues are
  documented inconsistently.
- **Permissions.** Adding sub-issues and dependencies needs triage access.
  Without push access, the REST API silently drops `type`, labels, milestone,
  and assignees on create. Read the issue back after creating it.
- **Issue fields.** Organizations can define issue fields such as Priority
  and Target date. These are team-owned values under Rule 6.

## Read before drafting

```sh
# Duplicates, open and closed
gh issue list --state all --search "guest checkout in:title"

# One item's place in the tree
gh issue view 41 --json issueType,parent,subIssues,subIssuesSummary,blockedBy
```

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

Without those flags, use the REST API:

- **Create.** `POST /repos/{owner}/{repo}/issues` accepts `type` (the type
  name) and `parent_issue_id` (the parent's integer `id`).
- **Sub-issue.** `POST /repos/{owner}/{repo}/issues/{parent_number}/sub_issues`
  takes `sub_issue_id`, the child's integer `id`.
  `gh api repos/OWNER/REPO/issues/57 --jq .id` returns it. The `id` from
  `gh issue view --json id` is a GraphQL node ID and does not work here.
- **Dependencies.** `POST .../issues/{issue_number}/dependencies/blocked_by`
  takes `issue_id`, the blocking issue's integer `id`.

## Projects

- From v2.97.0, `gh project item-edit <number> --owner <login> --url <issue-url> --field <name> --value <value>`
  sets one text, number, date, or single-select field per call.
- An iteration field needs `--iteration-id`. Get the ID from the GraphQL query
  above.
- Enable the hidden "Parent issue" and "Sub-issue progress" fields to see the
  tree.
- GitHub documents no roll-up of number fields, such as estimates, from
  sub-issues to their parent. When asked for an Epic's total, sum its
  sub-issues.
- Moving an item to Done may close the issue, so check the project's
  Workflows page before changing a status.

## Close and link

- A closing keyword such as `Fixes #57` in a commit message closes the issue
  when the commit reaches the default branch. Write `Part of #57` unless the
  commit meets every acceptance criterion.

## GitHub Enterprise Server versions

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
