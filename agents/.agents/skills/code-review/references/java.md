# Java review reference

Use when reviewing Java code in the diff. Apply this alongside the
main `code-review` skill workflow.

## Domain-modeling bias (apply first)

The Java ecosystem grew up on mutable POJOs. The `domain-modeling`
skill's doctrine is canonical:

- Prefer `record` (Java 14+) for value types over POJOs with getters
  and setters.
- Use `final` on fields, parameters, and locals by default; a
  non-final field that is never reassigned is a finding.
- Sealed classes / sealed interfaces (Java 17+) for sum types, with
  pattern-matching `switch` (Java 21+) instead of downcasting trees.
- `List.of(...)`, `Map.of(...)`, and `Collections.unmodifiableX`
  for read-only collections in public API.
- Push I/O into adapters; keep domain code pure and testable.
  Service classes that mutate shared fields outside construction are
  almost always wrong.

When in doubt, route to the `domain-modeling` skill.

## Tooling that should be passing

- Build: `./mvnw verify` or `./gradlew check` runs
  compile + tests + static analysis.
- Format: `spotless:check` (Maven) / `spotlessCheck` (Gradle).
- Static analysis: `spotbugs`, `errorprone`, or PMD if the
  project uses them. New warnings introduced by the diff are
  findings.
- Coverage: project-defined gate (JaCoCo). Don't drop coverage
  silently.
- IDE warnings off / `@SuppressWarnings("...")` needs a reason in
  the comment.

## High-signal review checks

- Null safety:
  - `Optional<T>` is for return types where absence is meaningful.
    Don't use `Optional<T>` as a field, parameter, or in a
    collection.
  - Public API should not return `null`; return `Optional` or an
    empty collection.
  - `@Nullable` / `@NonNull` annotations help static analysis;
    new code should annotate boundaries.
- Resource closing: `try-with-resources` for any `Closeable` /
  `AutoCloseable`. A new `InputStream`, `Connection`, or
  `PreparedStatement` opened with no scoped close is a finding.
- Exceptions:
  - Expected domain failures use named checked/unchecked exception
    types or explicit result variants, not generic
    `RuntimeException("message")`.
  - Don't catch `Exception` / `Throwable` at random; be specific.
  - Don't throw from `finally` (swallows the original).
  - Wrapping a checked exception as `RuntimeException` requires a
    useful message and the cause chain (`new RuntimeException(msg,
    e)`, not `new RuntimeException(msg)`).
  - Custom exceptions extend `RuntimeException` for unchecked,
    `Exception` for checked: pick deliberately.
- Concurrency:
  - Shared mutable state across threads needs `volatile`,
    `AtomicX`, `java.util.concurrent` collections, or a `Lock`:
    never plain `HashMap`.
  - `synchronized` on `this` or on a public reference is a
    Critical-tier finding (callers can lock on the same monitor).
    Prefer a private `final Object lock = new Object();`.
  - Virtual threads (Java 21+): blocking is fine. Before JDK 24,
    synchronized blocks pin the carrier: prefer `ReentrantLock`.
    JDK 24+ (JEP 491) no longer pins on `synchronized`.
- `equals` / `hashCode` / `toString`: must move together.
  `record` gives them for free; manual overrides need tests.
  Inheritance + `equals` is a known minefield (see Effective Java).
- Spring `@Transactional`:
  - Self-invocation (`this.method()`) bypasses the proxy and the
    transaction.
  - `@Transactional` on a private method is silently a no-op. On a
    protected or package-private method it is also a no-op before
    Spring 6.0, and with interface-based (JDK) proxies on any version.
  - Default rollback only on `RuntimeException`: checked exceptions
    don't roll back unless declared (`rollbackFor = ...`).
- Dependency injection: prefer constructor injection over field
  injection (`@Autowired private Foo foo;`). Constructor-injected
  classes are testable without Spring; field-injected ones aren't.
- Logging: SLF4J parameter form (`log.info("user {} did x",
  id)`) over string concatenation: lazy evaluation, no leak when
  level is off.
- Streams: stateful lambda inside `map` / `filter` is a finding;
  parallel streams almost always need a justification (CPU-bound,
  no shared state, large enough to amortise the fork-join overhead).
- `Date` / `Calendar`: stay in `java.time`: `Instant`,
  `LocalDate`, `ZonedDateTime`. Legacy `Date` in new code is a
  finding.
- Builds: a new dependency in `pom.xml` / `build.gradle` should
  match a real need; transitive bumps deserve a glance for known
  CVEs.

## Anti-patterns / red flags

- `catch (Exception e) { /* log and continue */ }`.
- `synchronized(this)` or `synchronized` on a public reference.
- `@Transactional` on a private method, or on a protected or
  package-private one before Spring 6.0 or with JDK proxies.
- Field injection (`@Autowired private Foo foo;`).
- `throw ex;` losing the cause chain.
- `Optional<T>` as a field or parameter.
- Mutable static state (`public static List<...> CACHE`).
- `String.format` / `+`-concat inside a log statement.
- New code using `java.util.Date` / `Calendar` / `SimpleDateFormat`.
- Returning `null` from a method whose contract says non-empty.

## Sources

- *Effective Java* (Bloch): canonical.
- Google Java Style Guide:
  <https://google.github.io/styleguide/javaguide.html>
- Java Records:
  <https://docs.oracle.com/en/java/javase/21/language/records.html>
- Spring `@Transactional`:
  <https://docs.spring.io/spring-framework/reference/data-access/transaction/declarative.html>
- Error Prone bug patterns: <https://errorprone.info/bugpatterns>
- SpotBugs bug descriptions:
  <https://spotbugs.readthedocs.io/en/latest/bugDescriptions.html>
