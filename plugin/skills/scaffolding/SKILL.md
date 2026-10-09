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
2. Research is free. Audit candidate dependencies without asking, then get
   approval before selecting or installing a structural runtime dependency
   (framework, database, ORM, auth client, SDK, state library, job queue),
   unless the user or the selected stack already named it.
3. Recommend one option per choice in priority order (language/runtime,
   deployment assumption, framework/template, framework-local choices) and
   name the tradeoff. Fresh web apps default to a mature framework unless the
   user asks for smaller.
4. Requested artifact names are literal. Create `tsconfig.json`,
   `package.json`, `pyproject.toml`, CI, or README by name; substitute a
   nearby config only with approval.
5. Commands are the contract: `test`, `lint`, `format`, `typecheck`, and
   `coverage` where applicable, and CI runs the same checks developers run.
   Every added config is consumed by a standard command.
6. `typecheck` runs a real type checker using the config added for it. A
   syntax check such as `node --check` is lint, not typecheck.
7. Fresh scaffolds get git and `.gitignore` before feature code, one package
   manager with a committed lockfile, one smoke test that can fail and pass,
   secret hygiene with `.env.example` placeholders, and a README with
   purpose, install, run, and test.
8. Prototypes keep the same command names even when checks are lightweight,
   and are promoted to the full checklist before production or collaboration.

## Workflow

1. Detect language, framework, existing conventions, and git state.
2. Present the Scaffold Decision Gate (Rule 1). Use
   `references/stacks/index.yaml` when a preset fits; otherwise
   `references/language-defaults.md` or official sources, naming the fallback.
3. After approval: git, package manager, standard commands, smoke test, CI,
   README, in that order.

## Tripwires

| Trigger | Do this instead | False alarm |
|---|---|---|
| "A similar config file will do" | Use the requested artifact name, or ask before substituting. | The user approved the substitute. |
| "`node --check` counts as typecheck" | Wire `typecheck` to a real type checker. | The language has no type checker and the documented equivalent is used. |
| "The command passed, so the scaffold works" | Verify the requirement, artifact, and command mapping, not only command success. | None. |
| "Set up git later" | Initialize git and `.gitignore` before feature code. | The user or environment blocks repo creation and the skip is reported. |
| "Approval would slow this down, just create the files" | Present Approve, Refine, and Cancel before scaffold mutation. | The request already specified every material setup choice. |
| "I'll pick the framework/ORM myself" | Research candidates freely; get approval before selecting or installing one. | The user or selected stack already named the choice, or it is a small dev-only utility. |

## Handoffs

- `domain-modeling`: first feature or domain data model.
- `proof`: first real feature test.
- `release`: CI becomes release or deploy automation.
- `security`: dependency audits, secret scanning, supply-chain gates.

## References

- `references/stacks/index.yaml`: load when a stack preset may fit.
- `references/language-defaults.md`: load when no preset fits.
