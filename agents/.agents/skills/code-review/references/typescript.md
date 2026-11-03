# TypeScript review reference

Use when reviewing TypeScript or Node.js, Workers, Bun, or SvelteKit code in
the diff.

## Domain-modeling bias

Route deeper modeling questions to `domain-modeling`.

- Prefer `readonly` fields, `as const`, and discriminated unions with
  literal-string tags over classes with mutable state and boolean flags.
- A class with no instance state becomes functions in a module.
- Money as `number` in an API or domain type is a finding. See
  `domain-modeling` Rule 8.

## Tooling

- CI gates: `tsc --noEmit` (or `tsc -b`), and type-aware ESLint with
  `strictTypeChecked` at `--max-warnings 0`. Published libraries also need a
  `package.json#exports` map, `attw`, and `publint`. When a gate is missing,
  review its concerns by hand and report the gap.
- New `@ts-ignore`, `@ts-expect-error`, or `eslint-disable` comments need a
  reason.

## tsconfig

- `strict` and `noUncheckedIndexedAccess` are blockers when missing from a
  new `tsconfig.json`.
- `exactOptionalPropertyTypes` is on by default. Defer it only at seams with
  loosely typed third-party code.
- New projects require `verbatimModuleSyntax`. Without it, esbuild, swc, and
  Babel cannot reliably elide type-only imports.
- Projects that target type-stripping runtimes need `erasableSyntaxOnly`.
- Module resolution follows the runtime. A library that ships `.d.ts` uses
  `module: nodenext`. A bundler-only app uses `module: preserve` with
  `moduleResolution: bundler`. `bundler` resolution can emit `.d.ts` imports
  without extensions, which Node consumers cannot resolve.

## Type system

- Block `as Foo` where `satisfies Foo` would do.
- Block every `any` without a TODO and a tracking issue. Use `unknown` at
  boundaries and force callers to narrow.
- A branded type is minted only by its validator. A bare `as UserId` blocks.
- The `default` arm of a `switch` over a closed union is `assertNever(x)` or
  `x satisfies never`. Missing exhaustiveness blocks.
- A type predicate or assertion function must check every property it
  claims, because the compiler trusts it. Inferred predicates miss truthy
  checks: `filter(x => !!x)` on `(number | undefined)[]` drops `0` and infers
  nothing. Use `!== undefined`.
- Always flag `as unknown as X`. Flag `!` on values that crossed an
  untrusted boundary (URL params, env vars, network input).
- A type parameter must appear in at least two positions in the signature,
  or it is a disguised `any`.
- Hand-rolled `DeepReadonly` breaks on `Map`, `Set`, `Date`, classes, and
  brands, and slows type checking.
- Under `exactOptionalPropertyTypes`, `name?: string` and
  `name: string | undefined` differ in `in` checks, spread, and
  serialization. Flag code that mixes them.
- `Date`, `Map`, `Set`, `bigint`, and class instances crossing a JSON
  boundary without conversion are findings.
- Numeric enums and `const enum` block. Use literal unions or `as const`
  objects.
- Error classes carry a `_tag` literal for narrowing, because `instanceof`
  fails across duplicate bundle copies.
- A generic `throw new Error("...")` for an expected domain outcome is a
  finding: use a named error class or a typed result variant.

## Parse at the boundary

- Block `as User` on JSON from the network or a database. Parse it.
- LLM outputs are a trust boundary and get parsed like any external input.
- Use one schema per direction: the create input differs from the stored
  shape. Warn on one schema serving both.

## Async

- Long-running async IO accepts `signal?: AbortSignal` and passes it down.
  Block new long-running APIs without one.
- `return promise` inside `try` without `await` skips the `catch`. Require
  `return await` there.
- Async callbacks passed where a void callback is expected drop rejections.
  This includes DOM and `EventEmitter` handlers and `forEach(async ...)`.
  Use `() => { void save().catch(report); }`.
- Express 4 does not catch async-handler rejections: call `next(err)` or
  upgrade to Express 5. Workers kill floating promises when the response
  returns: use `waitUntil`.

## Modules

- Block new internal barrel files in app code and every `export *`. The type
  checker, test runner, and dev server load every re-exported file. A
  library's single public entry point with named re-exports is fine.
- Block new CJS-only libraries. ESM-only libraries that use top-level await
  cannot be loaded by `require(esm)`, so dual-publish if CJS consumers
  matter.

## Type-check performance

- Watch for deep recursive conditional types, large unions intersected with
  each other, template-literal explosion, duplicate versions of type-heavy
  packages, and unannotated returns of complex generics.
- A diff that adds generic helpers to public types needs a before/after
  `--extendedDiagnostics` run. Reject growth over 10% in instantiations.

## Dependency injection

- Default to no container: factories that take a deps record and return
  bound functions. Tests pass a stub record.
- Warn on module-level `let` and on global singletons that hold live
  connections. They survive HMR, leak between tests, and break per-isolate
  runtimes like Workers.
- `AsyncLocalStorage` is for request id, user, and trace context, not
  general service plumbing.
