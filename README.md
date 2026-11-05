# Consult

Put the assistant back in coding assistant.

An open-source skills and workflow plugin for AI coding agents, built on one
rule: keep software simple enough to understand, change, and test.

## Context isn't just for agents

Agents can now write more code than anyone can read. One-shot a feature and
you get the code without the context of how it was built. Consult builds it
up with you in small, tested stages, keeps it simple, and walks you through
every change, so you know how it works as it grows.

### Iterate to build shared understanding

Coding agents were trained on finished code, not on how engineers got there.
Many engineers who use agents already steer them through plan, build, prove,
and review by hand. Consult writes that loop into the agent's skills, so it
runs at every stage without you asking for it.

You and the agent plan together, and you sign off on the plan and on big
calls. The agent builds the data and interfaces first and shows them to you
with their tests before it writes the logic on top. Every requirement gets a
test, and the agent breaks the code by hand to show each test can fail.
Before you commit, `/consult:code-review` in a fresh session gives you a
reviewer that tries to break the finished change.

### Hard-won lessons, for free

Consult is built from 25 years of web app, SRE, and developer platform
experience, with Rich Hickey's Simple Made Easy as its north star. It gives
your agent the habits and opinions that used to take years of mistakes to
learn.

- **Designs the data, interfaces, and APIs with you.** It asks before
  anything hard to undo, and gets on with the small stuff.
- **Builds in tested stages.** Data and interfaces, then logic. Every
  requirement gets a test.
- **Gets a second opinion when you ask.** Run `/consult:code-review` in a
  new session before you commit. The agent points it at the risky files.
- **Keeps the code simple.** Seven core rules apply to every change.
  Functions do one thing in about 25 to 30 lines. Nesting stays under three
  levels. A condition that joins checks with and/or gets a name that says
  what it means. Calculations stay apart from I/O, and nothing gets built
  that you didn't ask for.
- **Makes your calls.** Where there are several good ways to build
  something, Consult's house defaults pick one: a functional core, domain
  folders over layers, and Result-style errors. Where your project has
  already chosen, your project's choice wins.
- **Tells you what changed.** So you still know how the code works.

11 skills, 7 core rules, and about 2,200 tokens of always-on text.

## What loads

- **The core** (`agents/.agents/core.md`) prints at the start of every
  session. It holds the core rules, the house defaults, and how the agent
  works with you.
- **Seven skills** load on their own when their topic comes up: `proof`,
  `api`, `database`, `ui-design`, `scaffolding`, `domain-modeling`, and
  `git`.
- **Four skills** run only when you invoke them: `/consult:code-review`,
  `/release`, `/issue-tracking`, and `/documentation`. Claude Code ships its
  own `/code-review`, so Consult's keeps the `consult:` prefix.

## Install

Run each command inside Claude Code:

```
/plugin marketplace add dawson-design/consult
/plugin install consult@consult
```

To try a local checkout, run `claude --plugin-dir plugin`.

In Codex:

```sh
codex plugin marketplace add dawson-design/consult
codex plugin add consult@consult
```

Codex then asks you to trust Consult's SessionStart hook, which prints the
core. Install paths for Cursor and other agents will come later.

## Develop

```sh
make check      # validator, plugin drift, ruff, mypy, pytest
make plugin     # regenerate plugin/ after editing agents/.agents/
```

`AGENTS.md` has the authoring rules. `eval/README.md` covers the Harbor evals
that measure lift and cost against bare Claude Code.

## License

MIT
