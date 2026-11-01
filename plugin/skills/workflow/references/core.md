Consult is installed. When a request will change code, tests, config, or git
history, load the consult:workflow skill before you read any files, then load
each Consult skill its routing table matches before your first edit or commit.
Skip the skills for typo and wording fixes, one-line edits that change no
behavior, and questions that ask for no change. The core below applies either
way.

# Consult core

These rules apply to every code change, whether or not a Consult skill is
loaded. Skills cite them as core rules.

## Iron Law

`COMPLEXITY IS THE ENEMY: KEEP SOFTWARE SIMPLE ENOUGH TO UNDERSTAND, CHANGE, AND PROVE.`

## Rules

1. **Consult sets the engineering bar, and the host owns the mechanics.** When
   they conflict, Consult's bar wins, and the host decides how to meet it.
2. **Keep unrelated parts separate.** Make state and effects explicit. Keep
   calculations pure, and push I/O, database access, network calls, and
   mutation to the edges of the code you write. Keep the number of things a
   maintainer must understand together small.
3. **Build only what the user asked for.** Build the main behavior first unless
   safety or data loss requires an edge case now. Extract an abstraction only
   when code in more than one place serves the same purpose.
4. **Check existing tools before building one.** Look for a maintained library
   before writing code for a solved problem, and prefer mature, proven options
   unless the user asks for newer ones. Ask before adding a dependency.
5. **Write code a reader can follow in one pass.** This covers code you write
   or change; do not reshape untouched code to fit. Functions do one thing and
   stay around 25-30 lines. Conditionals and loops stay under three nesting
   levels; use guard clauses or extraction before adding another nested
   branch. Name each extracted function for its one job. A private function
   extracted this way is not an abstraction under core rule 3. A condition
   that joins two or more checks with a logical and/or (`&&`, `||`, `and`,
   `or`) gets a name that says what it means in plain English: a predicate
   function when reused, or a named local when used once. Null and bounds
   checks such as `items == null || items.length == 0` need no name. Build
   behavior by composing functions and plain data. Use inheritance only when
   a framework, a library, or the codebase's existing pattern requires it.
6. **Explain the change to the user.** Report what needs their attention
   first, then what changed, why it is better, what proves it, and what
   remains unproven.
7. **Ask whether backward compatibility is required** when a change alters
   behavior that callers outside the change, or stored data, depend on. Do
   not assume it is, and add no compatibility shim until the user answers. A
   fix that restores intended behavior needs no question, and a loaded
   skill's compatibility policy, such as `api`'s, takes precedence.
8. **Treat input that crosses a trust boundary as untrusted**, even when the
   request does not mention security. Parse or validate it before use.
9. **Static checks count as much as tests.** Before you commit or push, run
   the project's formatter, linter, and type checker along with its tests,
   and fix what they report in the code you changed. Do not rerun them after
   every edit. If a project past the prototype stage lacks any of them, say
   so and propose adding it. Adding one is a dependency under core rule 4.
