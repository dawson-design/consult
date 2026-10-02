# Linear, Azure DevOps, and GitLab

Load this reference when the tracker is Linear, Azure DevOps Boards, or
GitLab.

Facts were checked against each vendor's docs and changelog on 2026-10-02.
When a command or tool fails, recheck with `official-source-check`.

## Linear

| Level | Linear |
|---|---|
| Initiative | Initiative |
| Epic | Project |
| Issue | Issue |
| Sprint | Cycle |

- Initiatives can nest as sub-initiatives up to five levels (Enterprise
  plan), and one can have several parents. Rule 1 uses one level with one
  parent.
- An issue belongs to one project at a time. Project milestones are phases
  inside a project, not a hierarchy level. Sub-issues sit below an issue, and
  Rule 1 leaves them out.
- Cycles are per team, one to eight weeks long. Open issues roll over to the
  next cycle automatically.
- Issue relations are blocked by, blocks, related, and duplicate. Projects
  can also block other projects.
- Linear's MCP server is at `https://mcp.linear.app/mcp`, with a read-only
  endpoint at `https://mcp.linear.app/mcp/readonly` that suits status reports.
  It can create initiatives, projects, milestones, and issues. Its docs do not
  list tool names, so read them from the server. Linear has no official CLI.

## Azure DevOps Boards

The level names collide: an Azure DevOps Epic is this skill's Initiative.
State the mapping once in every draft.

| Process | Initiative | Epic | Issue |
|---|---|---|---|
| Agile | Epic | Feature | User Story |
| Scrum | Epic | Feature | Product Backlog Item |
| CMMI | Epic | Feature | Requirement |
| Basic | none | Epic | Issue |

- Tasks sit below the Issue level, and Rule 1 leaves them out.
- The Basic process has one portfolio level. An Initiative needs a custom
  portfolio backlog level, which can only be added at the top. Process
  changes are a `workflow` Rule 7 proposal for a process administrator.
- Each team decides whether bugs appear with requirements, with tasks, or
  not on backlogs. Follow the team's setting.
- Hierarchy uses the Parent-Child link, with one parent per item.
  Dependencies use Predecessor-Successor links, and peers use Related.
- Iterations are project-level paths that each team selects. Unfinished items
  stay in an iteration until someone moves them.
- `az boards work-item create --title "..." --type "User Story"` has no parent
  flag. Set the parent afterwards with
  `az boards work-item relation add --id <child> --relation-type parent --target-id <parent>`.
- Microsoft's MCP server runs locally with
  `npx -y @azure-devops/mcp <organization>`, or
  remotely at `https://mcp.dev.azure.com/{organization}` (public preview since
  March 2026, Entra-backed organizations only). `wit_work_item_write` creates
  and updates items and adds children under a parent.

## GitLab

| Level | Ultimate | Premium | Free |
|---|---|---|---|
| Initiative | Parent epic | No native level | No epics |
| Epic | Child epic | Epic | Label or milestone |
| Issue | Issue | Issue | Issue |

- Epics are group-level work items on Premium and Ultimate. Child epics need
  Ultimate. An issue belongs to at most one epic, and adding it to another
  moves it.
- Tasks sit below an issue, and Rule 1 leaves them out.
- OKR objectives are an Ultimate feature behind a feature flag and not ready
  for production. Do not use them for Initiatives.
- Iterations are Premium and Ultimate, set per group through iteration
  cadences. An automatic cadence runs one to four weeks, and roll over moves
  open issues to the next iteration.
- Links are relates to, blocks, and is blocked by. Blocking links need
  Premium, and linking epics needs Ultimate.
- `glab issue create --epic <id>` adds a new issue to an epic. `glab` has no
  iteration flag, and `glab work-items` is experimental.
- Quick actions such as `/set_parent`, `/epic`, `/iteration`, `/blocks`, and
  `/blocked_by` run when a description or comment is posted. They are tracker
  writes, so include them only in approved text.
- GitLab's MCP server (beta since 18.6, at `/api/v4/mcp`) offers
  `save_work_item` with `type_name` and `parent_id`, and `link_work_items`. It
  is on the Free tier from 19.2 and Premium before that, and an admin must
  allow it for the group or instance.
- The Epics REST API is deprecated. New integrations use the WorkItem GraphQL
  API.

## Sources

- [Linear conceptual model](https://linear.app/docs/conceptual-model)
- [Linear sub-initiatives](https://linear.app/docs/sub-initiatives)
- [Linear cycles](https://linear.app/docs/use-cycles)
- [Linear MCP server](https://linear.app/docs/mcp)
- [Azure Boards: choose a process](https://learn.microsoft.com/en-us/azure/devops/boards/work-items/guidance/choose-process)
- [Azure Boards: customize backlogs and boards](https://learn.microsoft.com/en-us/azure/devops/organizations/settings/work/customize-process-backlogs-boards)
- [az boards work-item relation](https://learn.microsoft.com/en-us/cli/azure/boards/work-item/relation)
- [Azure DevOps remote MCP server](https://learn.microsoft.com/en-us/azure/devops/mcp-server/remote-mcp-server?view=azure-devops)
- [GitLab epics](https://docs.gitlab.com/user/group/epics/)
- [GitLab child items](https://docs.gitlab.com/user/work_items/child_items/)
- [GitLab iterations](https://docs.gitlab.com/user/group/iterations/)
- [GitLab MCP server tools](https://docs.gitlab.com/user/model_context_protocol/mcp_server_tools/)
