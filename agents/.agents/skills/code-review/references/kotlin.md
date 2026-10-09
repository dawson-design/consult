# Kotlin review reference

Use when reviewing Kotlin code in the diff. Apply this alongside the
main `code-review` skill workflow.

## Domain-modeling bias (apply first)

Kotlin gives you the tools for domain-modeling design out of the box. The
`domain-modeling` skill's doctrine is canonical:

- Prefer `data class` with `val` properties over POJO-style classes
  with `var`.
- `val` over `var` everywhere; a `var` that is never reassigned is a
  finding.
- Sealed classes / sealed interfaces for sum types, with exhaustive
  `when` (no `else` branch: let the compiler enforce coverage).
- `copy()` over in-place mutation.
- Read-only collections (`List<T>` / `Map<K,V>`) in public API;
  `MutableList<T>` only when the contract genuinely requires it.
- Push I/O into adapters; keep domain code pure and testable.
  Service classes mutating fields outside construction are almost
  always wrong.

When in doubt, route to the `domain-modeling` skill.

## Tooling that should be passing

- Build: `./gradlew check` runs compile + tests + static
  analysis.
- Format: `./gradlew ktlintCheck` (or the project's chosen
  `spotlessCheck`).
- Static analysis: `./gradlew detekt`: new warnings introduced
  by the diff are findings; new `@Suppress("...")` needs a reason.
- Coverage: project-defined gate (JaCoCo / Kover). Don't drop
  coverage silently.

## High-signal review checks

- Null safety:
  - `!!` (the not-null assertion) is a Critical-tier red flag in
    production code. Each one needs a comment proving the value
    cannot be null at that point.
  - Long `?.` chains that silently lose errors deserve a `?: error("...")`
    or a proper handling branch.
  - Platform types (Java interop) are nullable in disguise; new
    interop boundaries should pin them as `T` or `T?` explicitly.
- `lateinit var`: only legitimate in DI / test fixtures /
  framework-injected fields. `lateinit` in plain domain code is a
  smell: the value should arrive through the constructor.
- Coroutines:
  - Expected domain failures use sealed result/error types or named
    exceptions, not generic `Exception("message")` / `error("message")`
    values that leak across domain boundaries.
  - Prefer structured concurrency: `coroutineScope { }`,
    `supervisorScope { }`. `GlobalScope.launch { }` is a leak in a
    long-running app: Critical.
  - Don't block coroutines with `Thread.sleep` or blocking I/O:
    use `withContext(Dispatchers.IO)` only at the boundary.
  - Cancellation: `CancellationException` must propagate; catching
    it without rethrow breaks structured concurrency.
  - `runBlocking` outside `main` / tests is suspicious.
  - Hot `Flow` (`SharedFlow`, `StateFlow`) shared without a scope
    leaks subscribers.
- `when` exhaustiveness: since Kotlin 1.7, a `when` statement over a
  sealed, enum, or Boolean subject must be exhaustive (compile
  error). Before 1.7, only the expression form is enforced:
  prefer it, or assign to `Unit` to force exhaustiveness.
- Extension functions: an extension on a type the project
  doesn't own is fine; one that shadows a member function is a bug
  (member wins). Flag any extension named the same as a method on
  the receiver.
- Inline / reified: useful for type tokens and avoiding
  reflection; `inline` on a non-trivial function bloats the call
  site: needs a reason.
- Visibility: Kotlin defaults to `public`. New top-level
  functions and classes meant to be internal should say `internal`
  explicitly.
- Companion objects / singletons: a `companion object` with
  mutable state is a hidden global. Flag it.
- Resource closing: `use { }` for any `Closeable`. Coroutine
  scope, flow collection, and file streams all need scoped cleanup.
- Spring `@Transactional` (when applicable): self-invocation
  bypasses the proxy; default rollback is `RuntimeException` only.
  Same caveats as Java.
- Logging: SLF4J parameter form (`log.info("user {} did x",
  id)`) over string concatenation; with Kotlin's interpolation it's
  tempting to write `log.info("user $id did x")` and lose lazy
  evaluation.

## Anti-patterns / red flags

- `!!` operator in non-test code.
- `lateinit var` outside DI / test fixtures.
- `GlobalScope.launch { }`.
- `runBlocking` in production code paths.
- `catch (e: CancellationException) { /* swallow */ }`.
- `data class` with mutable `var` properties.
- `companion object` with mutable shared state.
- `when` statement over a sealed type with no `else` and no
  exhaustiveness check (Kotlin before 1.7).
- Extension function shadowing a member function.
- `Thread.sleep` inside a coroutine.

## Sources

- Kotlin coding conventions:
  <https://kotlinlang.org/docs/coding-conventions.html>
- Kotlin coroutines guide:
  <https://kotlinlang.org/docs/coroutines-guide.html>
- Structured concurrency in Kotlin coroutines:
  <https://kotlinlang.org/docs/coroutines-basics.html#structured-concurrency>
- detekt rules: <https://detekt.dev/docs/rules/>
- ktlint rules: <https://pinterest.github.io/ktlint/latest/rules/standard/>
