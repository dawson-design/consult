# C# review reference

Use when reviewing C# code in the diff. Apply this alongside the main
`code-review` skill workflow.

## Domain-modeling bias (apply first)

C# has matured toward the `domain-modeling` skill's doctrine over the last few
versions; lean into the modern features:

- Prefer `record` (or `record struct`) with `init`-only properties
  over POJO-style classes with public setters.
- Pattern matching on closed type hierarchies (sealed classes,
  records implementing a common interface) for sum types.
- `with`-expressions over in-place mutation.
- `IReadOnlyList<T>`, `IReadOnlyDictionary<TK,TV>`, `ImmutableArray<T>`
  in public API where a mutable collection isn't required.
- Reject service classes that own mutable state the caller didn't
  ask for; flag mutable singletons unless the invalidation story is
  explicit.
- Parse at the boundary: validate controller inputs into typed
  domain values once and let downstream code trust them.

When in doubt, route to the `domain-modeling` skill.

## Tooling that should be passing

- `dotnet format --verify-no-changes`: formatting is enforced.
- `dotnet build -warnaserror`: clean build; new warnings are
  blockers unless an `EditorConfig` rule shifts in the same diff.
- `dotnet test`: narrow to the changed project first; full solution
  before merge.
- Project flags that should be set on every modern C# project:
  `<TreatWarningsAsErrors>true</TreatWarningsAsErrors>`,
  `<Nullable>enable</Nullable>`,
  `<ImplicitUsings>enable</ImplicitUsings>`. Missing any of these on
  a new project is a finding.

## High-signal review checks

- Nullable reference types: a method that returns `T?` but
  documents "never null" should return `T`. The null-forgiving
  operator (`!`) needs a one-line justification: it's a claim the
  reviewer must accept.
- Async:
  - `async void` outside event handlers: Critical, swallows
    exceptions.
  - `Task.Result` / `.Wait()` blocking on async: deadlock bait.
  - `ConfigureAwait(false)` is required in libraries to avoid
    deadlocks when a caller has a sync context. Missing it on a new
    library method is a finding.
  - `async` method with no `await` and a `.Result` inside: almost
    certainly wrong.
- `IDisposable` / `IAsyncDisposable`: any disposable opened in
  a method must be in a `using` / `await using` scope or explicitly
  handed off. Repeat offenders: `new HttpClient()` per call (use
  `IHttpClientFactory`), file streams without `using`, DB
  connections leaked across awaits.
- EF Core:
  - `.ToList()` then `.Where()` materialises before filtering.
  - `.Include()` chains causing cartesian explosion.
  - `AsNoTracking()` missing on read-only queries.
  - N+1 inside a loop iterating over a navigation property.
  - Raw SQL with string interpolation: use `FromSql` (EF Core 7+) or
    `FromSqlInterpolated` (earlier) / parameters, never `FromSqlRaw`
    with interpolated input.
- LINQ: `IEnumerable<T>` returned from a method that the caller
  enumerates twice will execute twice. Materialise (`.ToList()`)
  once when callers will re-enumerate; avoid materialising in tight
  pipelines.
- Exception handling: `catch (Exception)` swallowing without
  rethrow or log is a finding. Expected domain failures use named
  exception types or explicit result variants, not generic
  `Exception("message")` / `InvalidOperationException("domain
  outcome")` values that leak across domain boundaries. `throw ex;`
  reset the stack: use `throw;`.
- Pattern matching: `switch` over a closed hierarchy without an
  exhaustive default is brittle. New cases added later won't fail
  the compile. Prefer `_ => throw new UnreachableException()` or a
  static analyzer that enforces exhaustiveness.
- Allocations on hot paths: `string.Format` / interpolation in
  log statements without a level guard, `LINQ.ToList()` where
  `IEnumerable` would do, `params object[]` in tight loops. Match
  against the project's perf gates. Consider `Span<T>`,
  `ReadOnlySpan<T>`, `ArrayPool<T>` only when the perf case is real.
- Configuration secrets: connection strings, API keys, tokens
  must not be in checked-in `appsettings.json`. Look for
  user-secrets, environment variables, or a vault.
- Logging redaction: structured logging templates that
  interpolate user input (`_logger.LogInformation($"...")`) break
  message templates and can leak PII. Prefer
  `_logger.LogInformation("user {UserId} did X", id)`.
- DI lifetimes: `Singleton` capturing `Scoped` is a captive
  dependency: silent bug. Reviews should call out new
  registrations with mismatched lifetimes.

## Anti-patterns / red flags

- `async void` outside an event handler.
- `.Result` / `.Wait()` blocking on `Task`.
- `new HttpClient()` per call.
- `DateTime.Now` in domain logic: prefer `DateTimeOffset.UtcNow` or
  an injected `IClock`.
- Public mutable static state.
- `_logger.LogInformation($"... {sensitive}")`: interpolation
  inside a log template.
- `throw ex;` (use `throw;`).
- `catch (Exception) { /* swallow */ }`.
- `Singleton` capturing `Scoped` in DI registration.
- Mutable public properties on a class that pretends to be
  immutable.

## Sources

- .NET runtime conventions:
  <https://github.com/dotnet/runtime/blob/main/docs/coding-guidelines/coding-style.md>
- C# coding conventions:
  <https://learn.microsoft.com/en-us/dotnet/csharp/fundamentals/coding-style/coding-conventions>
- Async/await guidance (Stephen Cleary, "There Is No Thread"):
  <https://blog.stephencleary.com/2013/11/there-is-no-thread.html>
- EF Core performance:
  <https://learn.microsoft.com/en-us/ef/core/performance/>
- Framework Design Guidelines (de facto canon for public API
  shape):
  <https://learn.microsoft.com/en-us/dotnet/standard/design-guidelines/>
