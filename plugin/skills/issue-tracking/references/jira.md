# Jira

Facts were checked against Atlassian's docs, developer changelogs, and
pricing page on 2026-10-02. When a command fails, recheck with
`official-source-check`.

## Use the site's words

Jira Cloud renamed issues to work items in 2025, issue types to work types,
and projects to spaces. REST paths and JQL keep `issue` and `project`, and
JQL also accepts `space`. Jira Data Center still says issue and project.
Drafts use the words the site shows, and state the mapping to Initiative,
Epic, and Issue once.

## Map the levels

| Level | Jira |
|---|---|
| Initiative | A work type on a custom level above Epic |
| Epic | Epic (hierarchy level 1) |
| Issue | Story, Task, or Bug (level 0) |

Without a level above Epic, group an Initiative's Epics with a shared label
or component.

- **Subtasks** (level -1) sit below an Issue. Rule 1 leaves them out.
- **Levels above Epic need Jira Cloud Premium or Enterprise.** Adding one
  applies to every company-managed space and plan on the site, can break
  existing parent links, and cannot be undone. Treat it as a `workflow`
  Rule 2 proposal for a Jira admin, never an agent action.
- **Team-managed spaces** cannot add levels of their own. On Premium and
  Enterprise, a team-managed Epic can still take a company-managed Initiative
  as parent.
- **The Parent field** replaced Epic Link and Parent Link in Jira Cloud. Set
  `parent` for every level.

## Read before drafting

- `issue in portfolioChildIssuesOf("INIT-1")` returns all of an Initiative's
  descendants on Cloud. It is slow.
- Find Initiatives by work type, not `hierarchyLevel`, which does not cover
  custom levels above Epic.
- Required fields differ by work type. Read them before drafting, from the
  REST createmeta endpoints or the project's create screen.
- Sprint length comes from the board's sprints.

## Create the tree after approval

- **Rovo MCP Server** works on Jira Cloud only. Version 2 lists only primary
  tools, so find the rest with its discover tool. On Data Center, use the
  REST API.
- **Atlassian CLI.** The docs do not say whether
  `acli jira workitem create --parent` takes a key or an ID, and
  `acli jira workitem edit` documents no parent flag.
- **Links.** Admins can rename link types, so list them before linking.

## Close and link code

- Keep the key uppercase, such as `PROJ-42`, even in a branch name, so Jira
  links the work.
- Smart commits are on by default for newly connected repositories. Every
  smart-commit command, such as `PROJ-42 #comment`, `#time`, or `#done`, is a
  tracker write under Rule 7. A transition such as `#done` also needs every
  acceptance criterion met. A transition that needs other fields fails
  without an error.

## Jira Data Center

- Data Center keeps Epic Link and Parent Link. Use `"Epic Link" = KEY` for an
  Epic's Issues and `"Parent Link" = KEY` for an Initiative's Epics.
  `issuekey in childIssuesOf("INIT-1")` returns all descendants.

## Sources

- [Configure the work type hierarchy](https://support.atlassian.com/jira-cloud-administration/docs/configure-the-issue-type-hierarchy/)
- [Jira pricing](https://www.atlassian.com/software/jira/pricing)
- [JQL fields](https://support.atlassian.com/jira-software-cloud/docs/jql-fields/)
- [Work is the new collective term for items tracked in Jira](https://community.developer.atlassian.com/t/work-is-the-new-collective-term-for-items-tracked-in-jira/88552)
- [Deprecation of Epic Link and Parent Link in REST APIs](https://community.developer.atlassian.com/t/deprecation-of-the-epic-link-parent-link-and-other-related-fields-in-rest-apis-and-webhooks/54048)
- [Rovo MCP Server supported tools](https://developer.atlassian.com/cloud/rovo-mcp/guides/supported-tools/)
- [acli jira workitem create](https://developer.atlassian.com/cloud/acli/reference/commands/jira-workitem-create/)
- [Reference work items in your development work](https://support.atlassian.com/jira-software-cloud/docs/reference-issues-in-your-development-work/)
- [Process work items with smart commits](https://support.atlassian.com/jira-software-cloud/docs/process-issues-with-smart-commits/)
