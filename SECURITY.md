# Security Policy

## Reporting a vulnerability

Please report security issues privately rather than in public issues
or pull requests.

**Preferred channel:** open a private vulnerability report on GitHub at
<https://github.com/dawson-design/consult/security/advisories/new>.

Include:

- The skill, script, or manifest affected.
- Steps to reproduce the issue, including agent runtime and version.
- The observed impact, and what an attacker could do with it.
- Any suggested mitigation, if you have one.

Reports are acknowledged within seven days. A fix or mitigation
timeline is shared once the report is triaged.

## Scope

Consult ships skill content, install scripts, and plugin
manifests. Security-relevant surfaces include:

- `setup.sh` and any scripts under `scripts/`.
- Plugin manifests in `.claude-plugin/`, `plugin/.claude-plugin/`, and
  `plugin/.codex-plugin/`.
- Pre-commit hook in `.githooks/pre-commit`.
- Skill bodies that suggest commands, dependency installs, or
  destructive operations.

Out of scope: behavior of third-party agent runtimes (Claude Code,
Codex, Cursor (marketplace plugin or `~/.agents/skills/` discovery), Gemini CLI,
Google Antigravity, OpenCode, Copilot CLI), and
downstream projects that consume Consult.

## Supported versions

The most recent published version on `main` is supported. Older
versions and branches receive fixes only when the fix is trivial and
the report is high-impact.
