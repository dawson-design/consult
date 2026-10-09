# TypeScript review reference

Use when reviewing TypeScript or modern Node.js / Workers / Bun /
SvelteKit code in the diff. Apply this alongside the main `code-review`
skill workflow. Targets TS ≥ 5.5 with `strict` plus
`noUncheckedIndexedAccess` plus `verbatimModuleSyntax` as the floor.

## Domain-modeling bias (apply first)

Classes are easy to reach for in TS and rarely the right tool. The
`domain-modeling` skill's doctrine is canonical:

- Prefer `readonly` fields, `as const`, and **discriminated unions
  with literal-string tags** over classes with mutable state and
  boolean flags.
- A class with no instance state (only methods over its arguments)
  is a smell; convert to free functions in a module.
- `let` where `const` would do is a finding; intent matters.
- Make illegal states unrepresentable. `{ status: "ok"; value: T } |
  { status: "err"; error: E }` beats `T | null` plus an
  unrelated `error?: E`.
- Brand identity-ful primitives (`UserId`, `OrderId`, `Cents`,
  `SafeHTML`) so the structural type system stops treating them as
  interchangeable strings/numbers.
- Parse at the boundary into trusted internal shapes; let downstream
  code trust the types.

## Tooling that should be passing

- `pnpm tsc --noEmit` (or `tsc -b` in monorepos with project
  references): non-negotiable. Editor checks are not a substitute;
  they have different tsconfig resolution and stale state.
- `pnpm eslint --max-warnings 0`. Warnings linger and become noise.
  If you let them, the rule set isn't doing its job.
- `pnpm test`: narrow to the package under change. Vitest is the
  default in 2026; introducing Jest in a new project needs a stated
  reason (e.g. React Native test environment).
- For libraries: `attw --pack .` and `publint`: both required in
  CI. They mostly catch different problems.
- Lockfile (`pnpm-lock.yaml` / `package-lock.json` / `bun.lock`)
  committed; review the diff between manifest and lockfile for
  surprises (transitive bumps, new sources).

## tsconfig baseline (greenfield 2026)

```jsonc
{
  "compilerOptions": {
    "strict": true,
    "noUncheckedIndexedAccess": true,
    "exactOptionalPropertyTypes": true,
    "noImplicitOverride": true,
    "noFallthroughCasesInSwitch": true,
    "noPropertyAccessFromIndexSignature": true,
    "verbatimModuleSyntax": true,
    "isolatedModules": true,
    "erasableSyntaxOnly": true,
    "skipLibCheck": true,
    "moduleDetection": "force"
  }
}
```

- `strict` is non-negotiable; `noUncheckedIndexedAccess` is
  the new floor, catches an entire class of crashes by adding `|
  undefined` to indexed reads. Missing either in a new `tsconfig.json`
  is a blocker.
- `verbatimModuleSyntax` forces explicit `import type` and pairs
  with single-file transpilers (esbuild, swc, Babel). Pair with
  `@typescript-eslint/consistent-type-imports` for autofix.
- `exactOptionalPropertyTypes` distinguishes "absent" from
  "present and undefined." Real bug catcher; real friction at
  edges where third-party libs assume looser semantics. Default on,
  defer at messy seams.
- `erasableSyntaxOnly` (5.8+) forbids `enum`, `namespace`,
  parameter properties, and the legacy `<T>x` cast: required if
  you target Node 23+ type-stripping.
- Module resolution matches the runtime, not the author. Library
  shipping its own `.d.ts` → `module: nodenext` (so declarations
  work everywhere). Bundler-only project → `module: preserve` plus
  `moduleResolution: bundler`. `bundler` resolution can produce
  d.ts files that import without extensions, which Node consumers
  cannot resolve: it is infectious.

## Type system

- `satisfies` vs `:` vs `as`: three different tools.
  `satisfies` (4.9+) validates a value against a type without
  widening it. A colon annotation widens. `as` lies. Reach for
  `satisfies` whenever you want literal types preserved while
  validating shape. Block any `as Foo` where `satisfies Foo` would
  do the job.
- **`unknown` is the safe top type, `any` is a bug, `never` is the
  bottom.** `any` disables checking. Block every occurrence without
  a TODO and a tracking issue. Use `unknown` at API boundaries
  (`JSON.parse`, `fetch().then(r => r.json())`, message-bus payloads,
  catch variables) and force callers to narrow.
- Branded types must be reachable only through a validator.
  ```ts
  declare const brand: unique symbol;
  type Brand<T, B> = T & { readonly [brand]: B };
  type UserId = Brand<string, "UserId">;
  ```
  The discipline is that the only constructor of a `UserId` is the
  validator. A naked `as UserId` cast is the bug branding was meant
  to prevent: block on sight.
- Discriminated unions, exhaustiveness, `never` sentinel. Boolean
  flags admit impossible states; literal-string tags do not.
  Required: the `default` arm of every `switch` over a closed union
  is `assertNever(x)` (or the inline `x satisfies never` form). The
  `@typescript-eslint/switch-exhaustiveness-check` rule must be on.
  Block missing exhaustiveness on every PR.
- Type predicates and assertion functions must not lie. The
  compiler trusts the body absolutely. Block any `function isUser(v):
  v is User` whose body doesn't actually inspect every property it
  claims. TS 5.5 infers predicates from simple boolean arrows:
  watch the truthy-check trap: `filter(x => !!x)` on `(number |
  undefined)[]` doesn't infer because `0` is falsy. Use explicit
  `!== undefined` or `!= null`.
- Type assertions are escape hatches with a guest list.
  Acceptable: test fixtures, narrowing after a runtime check the
  compiler can't follow, JSON parse plus validation, branding the
  output of a validator. **Always-flag the double cast `as unknown
  as X`.** The compiler emits "conversion may be a mistake" because
  that is what it usually is. Same scrutiny for the non-null `!`
  operator on values that crossed an untrusted boundary (URL params,
  env vars, network input).
- Generics earn their keep, or get cut. A type parameter must
  appear in at least two distinct positions in the public
  signature, or it's doing nothing the caller can leverage. Block
  single-use generics (the "fancy `any`" anti-pattern). Warn on
  more than three or four type parameters on one signature.
- Inference helpers: prefer `Awaited`, `ReturnType`, `Parameters`
  over restating types you already declared. Use `NoInfer<T>` (TS
  5.4+) when one parameter should drive inference and another
  should only be checked.
- `readonly` is a contract, not a freeze. Default `readonly T[]`
  for parameters when the function doesn't mutate: quiet
  correctness win. `Readonly<T>` is shallow; the standard library
  has no deep-readonly. Hand-rolled `DeepReadonly` breaks on
  classes, `Map`, `Set`, `Date`, branded types, and tanks
  type-check perf.
- Annotate boundaries, infer interiors. Annotate function
  parameters always; annotate return types of exported functions
  and any reachable public API surface; let inference handle local
  variables and trivial returns. `isolatedDeclarations` (TS 5.5+)
  enforces this for libraries needing parallelisable d.ts emit.
- `interface` vs `type`: default to `type`. Switch to `interface`
  for object shapes that other shapes will `extends` in deep
  inheritance chains (extension is cached by name; intersections
  recompute each time: matters in hot type-check paths). Two
  gotchas: `type` aliases have an implicit `Record<PropertyKey,
  unknown>` index signature `interface` lacks; two interfaces with
  the same name in the same scope merge silently.

## Anti-patterns in `.ts` files

- Numeric enums admit out-of-domain values, leak runtime
  objects, bloat bundles. `const enum` is incompatible with
  `isolatedModules` and `verbatimModuleSyntax`. Both are forbidden
  under `erasableSyntaxOnly`. Replace with literal unions or `as
  const` objects:
  ```ts
  const Status = { Idle: "idle", Loading: "loading", Done: "done" } as const;
  type Status = (typeof Status)[keyof typeof Status];
  ```
  String enums are tolerable in app code that doesn't target
  type-stripping runtimes; numeric enums and `const enum` are
  blockers.
- `namespace` in `.ts` files: modules replaced these a decade
  ago. Allowed in `.d.ts` for ambient declarations only.
- `@ts-ignore` without comment: prefer `@ts-expect-error` with
  a reason; it auto-fails when the underlying issue is fixed.

## Error handling

- Catch variables are `unknown` under `useUnknownInCatchVariables`
  (which is in `strict`). Narrow before use. Block `catch (e: any)`
  and `catch (e)` treated as `Error` directly. Same for
  `Promise.prototype.catch(err => ...)` callbacks where `err` is
  implicitly `any`: enable
  `@typescript-eslint/use-unknown-in-catch-callback-variable`.
- Throwing string literals or plain objects breaks `instanceof`
  and `cause` chaining. Block.
- Subclass `Error` with a `_tag` literal for fast cross-realm
  narrowing (`instanceof` breaks across bundle boundaries with
  duplicate class identities):
  ```ts
  class NotFoundError extends Error {
    readonly _tag = "NotFoundError" as const;
    constructor(public readonly id: string, opts?: ErrorOptions) {
      super(`Not found: ${id}`, opts);
      this.name = "NotFoundError";
    }
  }
  ```
- Always preserve `cause` when re-throwing for context. Block
  catching and re-throwing without `{ cause }`, or replacing the
  original with a generic message.
  ```ts
  try { await db.query(sql); }
  catch (cause) { throw new DatabaseError("Failed to load user", { cause }); }
  ```
- Don't throw on expected failures. Throw for invariant
  violations, programmer errors, and at framework boundaries that
  catch and map. Use `Result<T, E>` (or `neverthrow`) for expected
  failures the caller must handle: validation, parse, IO that may
  legitimately fail. Don't leak `PostgresError` to HTTP handlers;
  don't leak raw `Error` objects to clients. Block handlers passing
  `err.message` straight to clients (PII and internals leak), and
  `catch {}` with no log. Block `throw "message"` and generic
  `throw new Error("domain outcome")`; use named error classes or
  typed result variants.

## Parse, don't validate

- A validator says "ok, continue." A parser says "give me unknown,
  I'll return a more precise type or an error." The parser encodes
  its proof in the type system so downstream code doesn't re-check.
  **Block every `as User` cast on JSON from the network or a
  database.**
- The 2025-2026 lineup all implement Standard Schema, the
  cross-library interface accepted by tRPC, Hono, TanStack Router,
  TanStack Form, and others.

  | Library | Best fit |
  |---|---|
  | Zod 4 | Default. APIs, tRPC, server validation. ~14× faster string and ~6.5× faster object than v3. |
  | Valibot 1.x | Client, edge, bundle-sensitive (Workers, mobile). ~1.4 kB. |
  | ArkType 2 | Server, perf-critical, complex unions. JIT compiler, auto-discriminates. |
  | Effect Schema | Apps already on Effect. |
  | TypeBox | When you need JSON Schema (Fastify, OpenAPI). Fastest of all (function-constructor codegen). |

- Validate at: HTTP/RPC inbound, env vars, filesystem reads,
  IPC, message queues, webhooks, LLM outputs, schemaless DB reads.
  Don't validate pure internal function-to-function calls inside
  the same trust boundary, or hot loops over data you parsed once.
- One schema per direction: `CreateUserInput` differs from `User`.
  Compose with `.pick`, `.omit`, `.extend`. Warn on a single schema
  used for both input and persistence.

## Async patterns

| Method | Use for |
|---|---|
| `Promise.all` | Fan-out where any failure is total |
| `Promise.allSettled` | Independent work; partial-success UIs |
| `Promise.any` | Redundant sources (mirror, cache + origin) |
| `Promise.race` | Rarely the right tool over `AbortSignal` |

- Block `Promise.all` over user-facing batches where one failure
  shouldn't nuke the whole batch: use `allSettled` and aggregate.
- `AbortController` is the platform-standard cancellation API.
  A function that does async IO must accept `signal?: AbortSignal`
  and pass it down. `AbortSignal.any([...])` and
  `AbortSignal.timeout(ms)` are baseline-supported across modern
  Node, browsers, Workers, Bun, and Deno. Block any long-running
  async API without a `signal` parameter: without it, React Strict
  Mode double-fires, race conditions on rapid input, and user
  navigation all leak.
- Floating promises are bugs. Block them with
  `@typescript-eslint/no-floating-promises` and
  `no-misused-promises`. The latter has the highest bug-yield of
  any rule in the plugin: catches `if (somePromise)`,
  `arr.forEach(async ...)`, `<button onClick={async () => {...}}>`.
- Serial `await` over independent IO is the await-in-loop
  antipattern. `Promise.all`, or `p-limit` when you need throttling.
- `return promise` inside `try` without `await`: the catch
  never fires:
  ```ts
  try { return fetchData(); } catch (e) { log(e); }      // wrong: catch never fires
  try { return await fetchData(); } catch (e) { log(e); } // right
  ```
  Enable `@typescript-eslint/return-await` (`"in-try-catch"` or
  `"always"`).
- `await using` and `Symbol.asyncDispose` (TS 5.2+, ES2025) for
  files, DB connections, locks, spans, subscriptions. Warn on new
  code that hand-rolls `try/finally` for cleanup or forgets to
  release on the error path.
- `Promise.withResolvers` (ES2024) replaces the
  `let resolve!: ...; new Promise(...)` dance for event-driven
  flows.
- Runtime gotchas: Express 4 swallows async-handler rejections
  (use `next(err)` or upgrade to Express 5); Cloudflare Workers
  kill floating promises when the isolate returns (use
  `event.waitUntil(promise)` for outliving work); DOM and
  `EventEmitter` handlers swallow rejections (wrap with `try/catch`
  or `.catch(reportError)`).

## Module boundaries

- Barrel files lose. When you `import { Button } from '@/ui'`,
  Node, Vitest, and the TS language server walk the entire
  `index.ts`, parse and bind every re-exported file, and recurse.
  Bundlers can tree-shake the runtime output; the type checker,
  test runner, and dev server cannot. Block new internal barrel
  files in app code. Block `export *`: hides name collisions and
  breaks tree-shaking. Acceptable: a library's single public-API
  entry point with explicit named re-exports.
- `package.json#exports` is how you draw the public API. Once
  set, anything not listed is unreachable
  (`ERR_PACKAGE_PATH_NOT_EXPORTED`). Block library publishing
  without `exports`. Block `types` listed after another condition:
  conditions are matched in object-key order and TypeScript ignores
  `types` unless first. Warn on an `./internal` subpath without
  SemVer explicitly excluded.
- Declaration files: default to generated
  (`tsc --emitDeclarationOnly`, `tsup --dts`, `tshy`). Block
  hand-edited `.d.ts` files alongside auto-generated ones: they
  drift.
- ESM-only is acceptable in 2026 for browser libraries, tools,
  CLIs, build plugins, anything where consumers can be assumed on
  Node ≥ 22.12 or a bundler. Dual-publish remains warranted for
  wide enterprise install bases on older Node, Jest setups still
  finishing ESM migration, or libraries using top-level await
  (which `require(esm)` cannot load). Block new CJS-only libraries
  in 2026. When dual-publishing, block a single `.d.ts` shared by
  ESM and CJS: ship `.d.cts` next to the `.cjs`. Warn on ESM-only
  without a stated Node floor in the README.

## Library author concerns

- `attw` and `publint` in CI for any published package.
  Non-negotiable.
- SemVer the type surface. Block breaking type changes shipped
  without a major version bump: narrowing return types, widening
  parameter types, removing overloads, renaming exported types,
  changing generic parameter defaults.
- `typescript` belongs in `peerDependencies` with a range like
  `">=5.4 <6.0"`, not `dependencies`.
- Variance annotations (`in`/`out`, TS 4.7+) are a library tool
  for deeply recursive types: block in app code without a stated
  reason.
- Type-level tests: block library code with non-trivial generics
  that ships no type tests. Inferred types are part of the API.
  `expectTypeOf` (Vitest) is the best ergonomic fit.

## Lint stack

- typescript-eslint flat config with
  `parserOptions.projectService: true` (stable v8, May 2024): uses
  the same `tsserverlibrary` ProjectService as VS Code, removes the
  need for `tsconfig.eslint.json`, supports project references,
  aligns lint type info with editor type info.
- High-yield rules to enable:
  - `no-floating-promises`, `no-misused-promises`, `await-thenable`:
    the async-correctness trio.
  - `switch-exhaustiveness-check`: survives refactors.
  - `no-unsafe-*` family: stops `any` infecting your code from
    third-party types.
  - `no-explicit-any`: forces explicit opt-out via comment.
  - `no-unnecessary-type-assertion`: redundant `as Foo` is hiding
    intent.
  - `restrict-template-expressions`: stops `${someObject}`
    rendering as `[object Object]` in logs.
  - `require-await`: async functions with no `await` are usually
    mistyped sync functions.
  - `return-await`: `return await` inside try/catch is required
    for the catch to fire.
  - `prefer-nullish-coalescing`: `??` vs `||` differs on `0` and
    `""`. Real bug source.
  - `prefer-optional-chain`: removes nested `&&` chains hiding
    null bugs.
  - `consistent-type-imports`, `consistent-type-exports`: pair
    with `verbatimModuleSyntax`.
  - `no-misused-spread`: catches `{ ...promise }`,
    `{ ...mapInstance }`, `[...string]` (decomposes emojis).
- Biome vs ESLint: Biome 2.x has type-aware rules built on a
  custom synthesizer (not `tsc`); coverage is roughly 75% of
  typescript-eslint for `no-floating-promises`. For
  production/library/safety-critical code, run Biome for format +
  syntactic + import sort, ESLint with `tseslint.configs.strictTypeChecked`
  for type-aware rules. Disable in ESLint anything Biome already
  covers.
- CI gates (non-negotiable in this order):
  - `tsc --noEmit` (or `tsc -b`): reports errors ESLint never
    will (`exactOptionalPropertyTypes`, `verbatimModuleSyntax`).
  - `eslint --max-warnings 0`.
  - `attw --pack` and `publint` for any published package.

## Performance (type-check and bundle)

- Slow type offenders, in frequency order: deep recursive
  conditionals walking string template types (fancy router types,
  ORM query builders); large unions intersected with each other
  (quadratic cost); string template explosion (`${A}-${B}` with
  100+ literals each = 10,000 members); duplicate package versions
  of complex types packages; inferred return types of complex
  generics: annotating the return type often turns 80s into
  500ms.
- Diagnose with `tsc --noEmit --extendedDiagnostics` and
  `tsc --generateTrace ./trace --incremental false`, then
  `npx @typescript/analyze-trace ./trace`. Warn on PRs adding
  generic helpers to public types without a before/after
  diagnostics run; reject regressions over 10% instantiations.
- Bundle size and types: types are erased: period. But these
  emit runtime code: `enum` (numeric and string), `namespace` with
  values (IIFE), decorators with `emitDecoratorMetadata`, `class`
  (fine, just understand it). `import type` is fully erased;
  `import { X }` for a type-only `X` may or may not be erased
  depending on the transpiler. `tsc` elides; esbuild, swc, and
  Babel cannot reliably elide without help. **`verbatimModuleSyntax`
  is what fixes this**: block new projects with it disabled.

## Dependency injection without a container

The strong default in 2026 is no container. Module-level
factories returning bound functions are dominant in modern Node,
Workers, and SvelteKit. Tests pass a stub object; no mocking
framework needed.

```ts
type Deps = { db: Db; logger: Logger; clock: () => Date };
export const createOrder = (deps: Deps) => async (input: NewOrder) => {
  const id = deps.clock().toISOString();
  await deps.db.insert("orders", { ...input, id });
  return id;
};
```

- Warn on global singletons holding live connections: they survive
  HMR, leak between tests, break in Workers (per-isolate).
- Warn on `AsyncLocalStorage` as primary service plumbing (request
  ID / user / traceparent are fine; arbitrary services are not).
- Block decorator-based containers (InversifyJS) in new Cloudflare
  Workers projects: `reflect-metadata` plus `emitDecoratorMetadata`
  plus legacy decorators interacts poorly with `verbatimModuleSyntax`,
  esbuild, and Workers bundle size. If you must, Awilix is the
  most defensible (no decorators, factory-based).

## Testing

- Vitest is the default. Co-located `foo.test.ts`; `expect` for
  assertions; `assert` only for null narrowing; `toMatchSnapshot`
  for complex output.
- `expectTypeOf` (Vitest, built on `expect-type`) for type-level
  tests on libraries with non-trivial generics. `.toEqualTypeOf`
  for strict equality, `.toExtend` for structural; `assertType`
  only checks assignability.
- Mock with `vi.mocked(...)` and a typed `vi.mock(import("./api"))`
  expression: survives rename refactors. Block `vi.mocked`
  replaced with `as Mock` casts; `eslint-plugin-vitest`
  `prefer-vi-mocked` catches this.
- Fixture with `satisfies`, not `:`. `satisfies User` preserves
  literal types where `: User` widens: affects readonly tuples and
  literal unions.

## Anti-patterns / red flags

- `: any` or `as any` in new code; `as unknown as T` without a
  comment justifying the validator wasn't appropriate.
- `// @ts-ignore` (use `@ts-expect-error` with a reason).
- `JSON.parse(req.body)` without a schema check.
- Branded type minted by `as Brand<...>` instead of through a
  validator.
- Single-use generic (type parameter appears in only one position).
- Module-level `let`: global mutable state, survives HMR, leaks
  between tests, breaks SSR / Workers.
- `if/else if` chain on a tagged union, or `switch` with no
  `assertNever` default.
- `?.` on a parameter that should be required (`User`, not
  `User | undefined`).
- Mixing `?` and `| undefined` under `exactOptionalPropertyTypes`
  (`{ name?: string }` vs `{ name: string | undefined }`: they
  behave differently in `'name' in obj`, spread, `JSON.stringify`,
  Mongo writes).
- Floating promise: `<button onClick={async () => { await save(); }}>`
  drops the rejection. Use
  `() => { void save().catch(showError); }`.
- `forEach(async ...)`, fire-and-forget loop with no awaiting.
- `return fetchData()` inside `try` without `await`.
- `Object.keys(config)` typed as `string[]` then used as
  `keyof typeof config` without an explicit cast.
- `for...in` on arrays (iterates inherited keys, gives `string`
  indices).
- `catch (e) { ... e.message ... }` without `instanceof Error`
  check.
- New `enum` (especially numeric); new `namespace` in `.ts`.
- New barrel file in app code; `export *`; `types` listed after
  another condition in `package.json#exports`.
- `Date`, `Map`, `Set`, `bigint`, `undefined` keys, or class
  instances crossing a JSON boundary unconverted. See
  [`domain-modeling/references/dates.md`](../../domain-modeling/references/dates.md) for
  the cross-language date discipline (UTC storage, RFC 3339 wire
  format).
- Money as `number` in any API or domain type; the IEEE 754 trap
  hits TS the same way it hits Python. See
  [`domain-modeling/references/money.md`](../../domain-modeling/references/money.md).
- Long-running async function with no `signal: AbortSignal` parameter.
- Runtime imports of type-only symbols under `verbatimModuleSyntax`.
- New code on `fp-ts` (in maintenance): redirect to Effect or
  vanilla TS.
- Library shipping without `attw` and `publint` in CI.
- `Math.random()` for anything security-sensitive (use
  `crypto.randomUUID` / `crypto.getRandomValues`).
- `console.log` in committed non-test code (use the project
  logger).

## Sources

- TypeScript Do's and Don'ts:
  <https://www.typescriptlang.org/docs/handbook/declaration-files/do-s-and-don-ts.html>
- Total TypeScript tsconfig cheat sheet:
  <https://www.totaltypescript.com/tsconfig-cheat-sheet>
- typescript-eslint rule index:
  <https://typescript-eslint.io/rules/>
- `attw` (Are The Types Wrong):
  <https://github.com/arethetypeswrong/arethetypeswrong.github.io>
- `publint`: <https://publint.dev/>
- Standard Schema interface:
  <https://standardschema.dev/>
- Zod: <https://zod.dev/> · Valibot: <https://valibot.dev/> ·
  ArkType: <https://arktype.io/>
- Effect: <https://effect.website/>
- Vitest: <https://vitest.dev/>
- Node.js best practices:
  <https://github.com/goldbergyoni/nodebestpractices>
- Hono routing/middleware: <https://hono.dev/docs/>
