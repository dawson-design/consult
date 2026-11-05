---
name: scaffolding
description: "House baseline for new projects and packages: stack choice, standard commands, real type checking, pinned toolchain, lockfile, smoke test, and CI. Use when creating a new project, package, or service, or adding baseline tooling to one."
---

# Scaffolding

## Iron law

No feature code before the toolchain proves it can fail and pass.

## Rules

1. Scaffold choices are the user's, decided at the plan checkpoint: project
   kind, language and runtime, deployment target, framework or template,
   and quality baseline. Skip the question only when the request already
   names every one.
2. Research candidate dependencies without asking, then get approval before
   choosing a structural one (framework, database, ORM, auth client, SDK,
   state library, job queue) the user or stack hasn't already named.
3. Recommend one option per choice, in this order: language and runtime,
   deployment, framework, framework-local choices. Name the tradeoff. A
   fresh web app starts on a mature framework unless the user asks for
   smaller. Pick from `references/stacks.md` when a preset fits.
4. Requested file, directory, script, and job names are literal. Create
   `tsconfig.json`, `package.json`, `pyproject.toml`, CI, or README by that
   name, and substitute a nearby config only with approval. The scaffold is
   done when each requested file and command exists, not only when the
   commands pass.
5. The commands are the contract: `test`, `lint`, `format`, `typecheck`, and
   `coverage` where it applies. CI runs the same checks developers run, and
   a pre-push hook runs format, lint, typecheck, and the fast tests. Every
   added config is used by a standard command.
6. `typecheck` runs a real type checker with the config added for it. A
   syntax check such as `node --check` is lint, not typecheck. A language
   with no type checker wires `typecheck` to its documented equivalent.
7. A fresh scaffold gets, before feature code: git and `.gitignore`, one
   package manager with a committed lockfile, the language version pinned
   in the ecosystem's file (`.python-version`, `.nvmrc`,
   `rust-toolchain.toml`, `go.mod`), one smoke test that can fail and pass,
   `.env.example` placeholders for secrets, and a README with purpose,
   install, run, and test. When the user or environment blocks repo
   creation, skip git and report it.
8. Prototypes keep the same command names even when the checks are light.

## References

- `references/stacks.md`: read before recommending a stack or tool for a new
  project. It holds the stack presets and per-language defaults.
