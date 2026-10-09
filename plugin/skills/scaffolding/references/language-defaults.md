# Language defaults

Cross-cutting language, runtime, and tooling stances that apply
regardless of which stack template gets scaffolded. These rules
extend beyond any single Backstage Software Template (see
`references/stacks/`); each template's `metadata.links` carries
authoritative framework / runtime / tooling docs.

Languages and ordering below mirror the stack catalog
(`references/stacks/<language>/`); the catalog is the source of
truth for which languages Consult scaffolds. Package-manager defaults
are named below when they are part of the scaffold decision.

## TypeScript / Node

- Modern Node strips TypeScript natively for single-file scripts
  and simple CLIs, no flag, no loader. Reach for a bundler or
  `tsc` only when types, emit, declaration files, or non-`.ts`
  compile steps are genuinely required.
- When a TypeScript runner is needed (decorators, legacy TS
  features), use `tsx`. Do not reach for `ts-node`.
- For bundled builds use the framework's bundler (Vite, SvelteKit,
  Wrangler) rather than hand-wiring esbuild/tsc.

## Python

- uv consolidates pip, pip-tools, pipx, Poetry, pyenv, virtualenv
  into a single tool. Do not layer any of those on top.
- Avoid raw `http.server` or hand-rolled WSGI/ASGI routing for web
  apps.
- Use `pyproject.toml` managed by uv with `uv.lock`.

## Java

The `java/` catalog covers Java-first frameworks (Javalin, Quarkus,
Spring Boot). Both Java and Kotlin source are supported via the
`language_flavor` parameter; pick `java/` when the framework
itself is Java-shaped. For Kotlin-first frameworks (coroutine-
native Ktor, Kotlin DSL routing) see the `kotlin/` catalog and
the section below.

- Build tool: Gradle with the Kotlin DSL (`build.gradle.kts`,
  `settings.gradle.kts`). Groovy DSL is legacy; Maven only when the
  repo is locked to it.
- JDK baseline: target the current LTS JDK; check the OpenJDK
  roadmap before picking. Do not start on a non-LTS line.
- Use a Gradle version catalog (`gradle/libs.versions.toml`) for
  shared dependency versions in any multi-project build.
- Avoid hand-rolled servlet/Jetty/Netty routing unless the project
  is a library/teaching example.

## Kotlin

The `kotlin/` catalog covers Kotlin-first frameworks (Ktor); the
same build-tooling stance as Java applies (Gradle Kotlin DSL, JDK
LTS, version catalog). Use the `java/` templates with
`language_flavor: kotlin` when you want Kotlin source against a
Java-shaped framework (Javalin, Quarkus, Spring Boot).

- Kotlin compiler: K2 (modern front-end) is the default compiler
  since Kotlin 2.0.
- Concurrency: Kotlin coroutines + structured concurrency for new
  async code; avoid mixing with raw threads or callback-style APIs
  unless interop with a Java library forces it.
- DI: pick Koin or Kodein when DI is wanted; Spring DI only when
  picking a Spring template; Quarkus CDI only when picking a Quarkus
  template. Ktor itself stays DI-agnostic.
- Persistence: Exposed (JetBrains' Kotlin SQL framework) is the
  Kotlin-native default; jOOQ when a typesafe SQL DSL is the
  priority; JDBI when SQL-with-object-mapping is enough.

## Ruby

- Bundler with `Gemfile` + `Gemfile.lock`.
- Target the current stable Ruby. Ruby does not enable YJIT by
  default; Rails 7.2+ turns it on for new apps on Ruby 3.3+.
- Avoid raw Rack app scaffolds for web apps unless the project is a
  tiny library/teaching example.

## Go

- The stdlib `net/http` `ServeMux` (method matching such as
  `GET /users/{id}`, wildcards, `Request.PathValue()`) subsumes
  most of what third-party routers were historically used for.
  `gorilla/mux` was archived in 2022 and revived in 2023, but the
  stdlib covers its common uses; do not scaffold it into new projects.
- Reach for a heavier framework only when the app actually needs
  the ecosystem, middleware set, or FastHTTP perf profile.

## Rust

- Use the current stable edition for new crates; pin MSRV to what
  the edition requires and bump it intentionally.
- Async runtime: Tokio (default).
- Diesel is acceptable only for repos already on it; new code
  should pick SeaORM (async-first ORM) or sqlx (compile-time-
  checked SQL).
- Avoid hand-rolled hyper/TCP servers for web apps unless protocol
  work is the point.

## C#

- Use Central Package Management (`Directory.Packages.props`) in
  any solution with more than one project.
- Target the current LTS .NET release. Use STS only when its
  features are load-bearing.
- Native AOT is available across ASP.NET Core, MAUI, and EF Core
  pre-compiled queries; opt in when startup time and memory
  footprint justify the build-time cost.
- Avoid hand-rolled HTTP listeners for web apps.

## F#

- Same .NET runtime stance as C# (LTS baseline, Central Package
  Management, dotnet CLI + NuGet).
- Native AOT's limits on dynamic code are stricter for F# than C#;
  enabling it usually rules out reflection-heavy libraries
  (Newtonsoft.Json, parts of EF Core's runtime model). Verify each
  dependency's AOT compatibility before turning it on.
- Test runner: Expecto or xUnit. Format with Fantomas.
- For new HTTP code prefer Giraffe-style functional handlers over
  MVC controllers; reach for Saturn when Rails-inspired
  conventions are wanted (template `fsharp/web-saturn`).

## Elixir

- Mix with Hex dependencies and `mix.lock`.
- Elixir features to rely on for new code (1.18+): type checking of
  function calls, built-in JSON, and `mix format --migrate` to
  carry older patterns forward.
- Phoenix uses Bandit as its default web server; Cowboy is legacy.
  LiveView is the default interactive tier; reach for channels only
  when LiveView is not the shape of the problem.

## Clojure

- deps.edn (over Leiningen) is the modern project layout for new
  projects.
- Reitit (data-driven router) is the modern preferred Ring router;
  Compojure is older.
- Component lifecycle: Integrant is the most modern of the
  Component / mount / Integrant trio for new services.
- Schema / validation: malli for new code (domain-modeling); `clojure.spec`
  is built-in but more verbose for everyday use.

## Frontend tooling (TypeScript-adjacent)

- Small/demo/prototype frontend without an existing framework:
  Alpine.js + HTMX. Larger app: SvelteKit (templated by
  `typescript/fullstack-sveltekit`).
- React/Next.js only when the user asks, an existing repo uses it,
  or a React-only library/team constraint dominates.
- Don't treat server-rendered HTML with inline JavaScript inside
  the backend entrypoint as the default "minimal" frontend.

## Documentation tooling

- For large projects: Material for MkDocs by default, regardless of
  app language or framework, unless the repo/user/publishing
  constraint chooses another. It has been in maintenance mode since
  November 2025 (fixes only; new work moved to Zensical).
