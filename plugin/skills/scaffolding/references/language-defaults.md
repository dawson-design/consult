# Language defaults

House defaults for the Scaffold Decision Gate when the repo has not already
chosen. They apply with or without a stack preset from `stacks.md`.

## TypeScript / Node

- Use pnpm, with Biome for lint and format.
- Modern Node runs TypeScript directly by stripping types, with no flag or
  loader; check the target Node version. Scripts and simple CLIs need no
  build step, but `typecheck` still runs `tsc --noEmit` (Rule 6). Emit with
  `tsc` or a bundler only for JavaScript output or declaration files, and
  use the framework's bundler (Vite, SvelteKit, Wrangler) rather than
  hand-wiring esbuild or `tsc`.
- When a TypeScript runner is needed (decorators, legacy TS features), use
  `tsx`. Do not reach for `ts-node`.

## Native builds (.NET and JVM)

- Leave Native AOT and GraalVM native image off unless startup time or
  memory footprint justify the build cost.
- Native AOT is stricter for F# than C#. It rules out reflection-heavy
  libraries such as Newtonsoft.Json and parts of EF Core's runtime model, so
  check each dependency before enabling it.

## Rust

- Diesel is acceptable only for repos already on it; new code should pick
  SeaORM (async-first ORM) or sqlx (compile-time-checked SQL).

## Clojure

- deps.edn over Leiningen, and malli over `clojure.spec`, for new projects.

## Frontend

- React/Next.js only when the user asks, an existing repo uses it, or a
  React-only library/team constraint dominates.
- Don't treat server-rendered HTML with inline JavaScript inside the backend
  entrypoint as the default "minimal" frontend.
