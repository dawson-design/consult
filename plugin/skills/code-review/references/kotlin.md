# Kotlin review reference

Use when reviewing Kotlin code in the diff.

## Domain-modeling bias

Route deeper modeling questions to `domain-modeling`.

- Match sealed types with `when` and no `else` branch, so the compiler
  reports a missing case.
- `lateinit` is only for DI, test fixtures, or framework-injected fields.
  Domain values arrive through the constructor.
- Keep I/O in adapters. Mutable fields in service classes, `object`
  declarations, or companion objects are hidden shared state.

## Checks

- New detekt warnings in the diff are findings. `@Suppress` needs a reason.
- Each `!!` in production code needs a comment proving the value cannot be
  null there.
- Pin Java platform types to `T` or `T?` at new interop boundaries.
- Expected domain failures use sealed result types or named exceptions, not
  `error("...")` or a generic `Exception("...")`.
- `catch (e: Exception)` and `runCatching` in suspend code swallow
  `CancellationException`. Rethrow it.
- Spring `@Transactional` rolls back only on `RuntimeException` and `Error`.
  Kotlin has no checked exceptions, so a thrown `Exception` subclass commits
  the transaction unless `rollbackFor` names it.
