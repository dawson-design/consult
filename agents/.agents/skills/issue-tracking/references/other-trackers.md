# Linear, Azure DevOps, and GitLab

Facts were checked against each vendor's docs and changelog on 2026-10-02.
When a command or tool fails, recheck the official docs. Read MCP
tool names and setup from the server or its Sources link.

Rule 1 leaves out items below an Issue: Linear sub-issues, Azure DevOps
Tasks, and GitLab tasks. Rule 3 reads sprint length from the team's Linear
cycles, the Azure DevOps team's selected iterations, or the GitLab group's
iteration cadence (Premium and Ultimate).

## Linear

| Level | Linear |
|---|---|
| Initiative | Initiative |
| Epic | Project |
| Issue | Issue |
| Sprint | Cycle |

- Initiatives can nest as sub-initiatives and take several parents. Use one
  Initiative level with one parent.
- An issue belongs to one project at a time. Project milestones are phases
  inside a project, not a hierarchy level.
- Projects can block other projects.

## Azure DevOps Boards

The level names collide: an Azure DevOps Epic is this skill's Initiative.
State the mapping once in every draft.

| Process | Initiative | Epic | Issue |
|---|---|---|---|
| Agile | Epic | Feature | User Story |
| Scrum | Epic | Feature | Product Backlog Item |
| CMMI | Epic | Feature | Requirement |
| Basic | none | Epic | Issue |

- On the Basic process, an Initiative needs a custom portfolio backlog
  level, which a process administrator adds.
- Each team decides whether bugs appear with requirements, with tasks, or
  not on backlogs. Follow the team's setting.
- Dependencies use Predecessor-Successor links.

## GitLab

| Level | Ultimate | Premium | Free |
|---|---|---|---|
| Initiative | Parent epic | No native level | No epics |
| Epic | Child epic | Epic | Label or milestone |
| Issue | Issue | Issue | Issue |

- Epics live in groups, not projects. An issue belongs to at most one epic,
  and adding it to another moves it.
- OKR objectives are an Ultimate feature behind a feature flag and not ready
  for production. Do not use them for Initiatives.
- Quick actions such as `/set_parent`, `/epic`, `/iteration`, `/blocks`, and
  `/blocked_by` run when a description or comment is posted. They are tracker
  writes, so include them only in approved text.
- GitLab's MCP server works only after an admin allows it for the group or
  instance.
- The Epics REST API is deprecated. New integrations use the WorkItem GraphQL
  API.

## Sources

- [Linear conceptual model](https://linear.app/docs/conceptual-model)
- [Linear sub-initiatives](https://linear.app/docs/sub-initiatives)
- [Linear cycles](https://linear.app/docs/use-cycles)
- [Linear MCP server](https://linear.app/docs/mcp)
- [Azure Boards: choose a process](https://learn.microsoft.com/en-us/azure/devops/boards/work-items/guidance/choose-process)
- [Azure Boards: customize backlogs and boards](https://learn.microsoft.com/en-us/azure/devops/organizations/settings/work/customize-process-backlogs-boards)
- [Azure DevOps remote MCP server](https://learn.microsoft.com/en-us/azure/devops/mcp-server/remote-mcp-server?view=azure-devops)
- [GitLab epics](https://docs.gitlab.com/user/group/epics/)
- [GitLab child items](https://docs.gitlab.com/user/work_items/child_items/)
- [GitLab iterations](https://docs.gitlab.com/user/group/iterations/)
- [GitLab MCP server tools](https://docs.gitlab.com/user/model_context_protocol/mcp_server_tools/)
