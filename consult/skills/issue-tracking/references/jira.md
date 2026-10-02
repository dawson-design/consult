# Jira

Load this reference when the tracker is Jira Cloud or Jira Data Center.

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

| Level | Jira | Without a level above Epic |
|---|---|---|
| Initiative | A work type on a custom level above Epic | No native level. Propose one to a Jira admin, or a label or component shared by the Epics. |
| Epic | Epic (hierarchy level 1) | Epic |
| Issue | Story, Task, or Bug (level 0) | Story, Task, or Bug |

- **Subtasks** (level -1) sit below an Issue. Rule 1 leaves them out.
- **Levels above Epic need Jira Cloud Premium or Enterprise.** A Jira admin
  creates the work type, adds it to the work type scheme, then adds the level
  under Settings > Work items > Work type hierarchy. The change applies to
  every company-managed space and plan on the site. It can break existing
  parent links and cannot be undone. Treat it as a `workflow` Rule 7 proposal
  for the admin, never an agent action.
- **Team-managed spaces** cannot add levels of their own. On Premium and
  Enterprise, a team-managed Epic can still take a company-managed Initiative
  as parent.
- **The Parent field** replaced Epic Link and Parent Link in Jira Cloud. Set
  `parent` for every level.
- **Estimates.** Company-managed spaces use "Story points" and team-managed
  spaces use "Story point estimate". They are different fields with
  site-specific IDs. Both are team-owned values under Rule 6.

## Read before drafting

```text
parent = PROJ-10                          direct children: an Epic's Issues or an Initiative's Epics
issuetype = Epic AND statusCategory != Done
project = PROJ AND text ~ "guest checkout"    duplicates
sprint in openSprints() AND project = PROJ
issue in portfolioChildIssuesOf("INIT-1")     all descendants, slow, Cloud
```

- `hierarchyLevel = 1` finds Epics, but the field does not cover custom
  levels above Epic.
- Required fields differ by work type. Read them before drafting with the
  REST createmeta endpoints, the MCP tool `getJiraIssueTypeMetaWithFields`, or
  the project's create screen.
- Sprint length comes from the board's sprints, through the MCP tool
  `listJiraBoardSprints` or `acli jira board list-sprints --id <board-id>`
  (acli v1.3.5 or later).

## Create the tree after approval

Create parents first and pass each child its parent's key.

- **Rovo MCP Server** (Jira Cloud only, GA 2026-02-04, v2 at
  `https://mcp.atlassian.com/v2/mcp`). Write tools include `createJiraIssue`,
  `editJiraIssue`, `createJiraIssueLink`, and `transitionJiraIssue`, and
  `searchJiraIssuesUsingJql` runs JQL. Version 2 lists only primary tools, so
  find the rest with its discover tool. Atlassian's sample skill passes
  `cloudId`, `projectKey`, `issueType`, `summary`, a Markdown `description`,
  and `parent`.
- **Atlassian CLI.**
  `acli jira workitem create --summary "..." --project PROJ --type Story --parent <parent>`
  creates an item, `--from-json` takes a full definition, and
  `acli jira workitem link create --out PROJ-1 --in PROJ-2 --type Blocks`
  links two items. The docs do not say whether `--parent` takes a key or an
  ID, and `acli jira workitem edit` documents no parent flag.
- **REST API v3.** `POST /rest/api/3/issue` sets the parent with
  `fields.parent` as `{"key": "PROJ-10"}`. The description, multi-line text
  fields, and comments must be Atlassian Document Format (ADF), not Markdown.
- **Links.** The defaults include blocks / is blocked by and relates to.
  Admins can rename them, so list them first with `listJiraIssueLinkTypes`.
- **Sprints.** `POST /rest/agile/1.0/sprint/{sprintId}/issue` moves items
  into a sprint. Adding to an active sprint shows as a scope change in sprint
  reports. Under Rule 6, only the user decides it.

## Close and link code

- An uppercase key such as `PROJ-42` in a branch name, commit message, or PR
  title links the work in Jira when the GitHub for Atlassian app or Bitbucket
  is connected.
- Smart commits run commands from commit messages: `PROJ-42 #comment ...`,
  `PROJ-42 #time 2h`, and a transition such as `PROJ-42 #done`. They are on by
  default for newly connected repositories. A transition command is a tracker
  write, so use one only when the user asked and every acceptance criterion
  is met. A transition that needs other fields fails without an error.
- Completing a sprint moves unfinished items to the backlog or another
  sprint. All subtasks must be Done first.

## Jira Data Center

- Data Center keeps Epic Link and Parent Link. Use `"Epic Link" = KEY` for an
  Epic's Issues and `"Parent Link" = KEY` for an Initiative's Epics.
  `issuekey in childIssuesOf("INIT-1")` returns all descendants.
- Levels above Epic are set under Advanced Roadmaps hierarchy configuration.
- The Rovo MCP Server does not reach Data Center. Use the REST API.
- Atlassian ends Data Center support on 2029-03-28.

## Sources

- [Configure the work type hierarchy](https://support.atlassian.com/jira-cloud-administration/docs/configure-the-issue-type-hierarchy/)
- [Jira pricing](https://www.atlassian.com/software/jira/pricing)
- [JQL fields](https://support.atlassian.com/jira-software-cloud/docs/jql-fields/)
- [Work is the new collective term for items tracked in Jira](https://community.developer.atlassian.com/t/work-is-the-new-collective-term-for-items-tracked-in-jira/88552)
- [Deprecation of Epic Link and Parent Link in REST APIs](https://community.developer.atlassian.com/t/deprecation-of-the-epic-link-parent-link-and-other-related-fields-in-rest-apis-and-webhooks/54048)
- [Rovo MCP Server supported tools](https://developer.atlassian.com/cloud/rovo-mcp/guides/supported-tools/)
- [acli jira workitem create](https://developer.atlassian.com/cloud/acli/reference/commands/jira-workitem-create/)
- [Jira REST API v3](https://developer.atlassian.com/cloud/jira/platform/rest/v3/intro/)
- [Reference work items in your development work](https://support.atlassian.com/jira-software-cloud/docs/reference-issues-in-your-development-work/)
- [Process work items with smart commits](https://support.atlassian.com/jira-software-cloud/docs/process-issues-with-smart-commits/)
