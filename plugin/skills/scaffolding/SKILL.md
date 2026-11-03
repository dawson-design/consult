---
name: scaffolding
description: "Setting up a new project or package: scripts, test, lint, typecheck, CI, tooling. Load before creating files."
---

# Scaffolding

## Iron Law

`NO FEATURE CODE BEFORE THE TOOLCHAIN PROVES IT CAN FAIL AND PASS.`

A scaffold is done only when a clean clone can install, check, test, and run
the baseline without local knowledge.

## When to Use

- Starting a new repo or app, or adding missing package management, linting,
  formatting, typechecking, testing, coverage, or CI.

## When NOT to Use

- Adding a feature to a healthy project; use the domain skill plus `proof`.
- Release pipeline beyond baseline CI; use `release`.
- UI design choices after the framework is chosen; use `ui-design`.

## Rules

1. The user owns scaffold choices. Before creating files, installing packages,
   or running generators, present a Scaffold Decision Gate (project intent
   and kind, language/runtime, deployment assumption, framework/template,
   quality baseline, files and commands) with this menu, and wait:
   1. Approve: create files, install packages, run generators
   2. Refine: change the scaffold plan
   3. Cancel: stop scaffolding

   Skip the gate only when the request already names every material setup
   choice.
2. Research is free. Audit candidate dependencies without asking, then get
   approval before selecting or installing a structural runtime dependency
   (framework, database, ORM, auth client, SDK, state library, job queue),
   unless the user or the selected stack already named it.
3. Recommend one option per choice in priority order (language/runtime,
   deployment assumption, framework/template, framework-local choices) and
   name the tradeoff. Fresh web apps default to a mature framework unless the
   user asks for smaller.
4. Requested file, directory, script, and job names are literal. Create
   `tsconfig.json`, `package.json`, `pyproject.toml`, CI, or README by name;
   substitute a nearby config only with approval. The scaffold is done when
   each requested file, directory, and command exists, not only when the
   commands pass.
5. Commands are the contract: `test`, `lint`, `format`, `typecheck`, and
   `coverage` where applicable. CI runs the same checks developers run, and a
   pre-push hook runs format, lint, typecheck, and the fast tests locally, so
   commits stay quick. Every added config is consumed by a standard command.
6. `typecheck` runs a real type checker using the config added for it. A
   syntax check such as `node --check` is lint, not typecheck. For a
   language with no type checker, wire `typecheck` to its documented
   equivalent.
7. Fresh scaffolds get git and `.gitignore` before feature code, one package
   manager with a committed lockfile, the language version pinned in the
   ecosystem's file (`.python-version`, `.nvmrc`, `rust-toolchain.toml`,
   `go.mod`), one smoke test that can fail and pass,
   secret hygiene with `.env.example` placeholders, and a README with
   purpose, install, run, and test. When the user or environment blocks repo
   creation, skip git and report the skip.
8. Prototypes keep the same command names even when checks are lightweight,
   and are promoted to the full checklist before production or collaboration.

## Workflow

1. Detect language, framework, existing conventions, and git state.
2. Present the Scaffold Decision Gate (Rule 1). Pick a preset from
   `references/stacks.md` when one fits, and apply
   `references/language-defaults.md`; when neither covers a choice, use
   official sources and name the fallback.
3. After approval: git, package manager, standard commands, smoke test, CI,
   README, in that order.

## Handoffs

- `domain-modeling`: first feature or domain data model.
- `proof`: first real feature test.
- `release`: CI becomes release or deploy automation.
- `security`: dependency audits, secret scanning, supply-chain gates.

## References

- `references/stacks.md`: load before recommending a stack for a new
  project.
- `references/language-defaults.md`: load when choosing language, runtime,
  or tooling for the Gate.
