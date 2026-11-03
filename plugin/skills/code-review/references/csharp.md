# C# review reference

Use when reviewing C# code in the diff.

## Domain-modeling bias

Route deeper modeling questions to `domain-modeling`.

- Prefer `record` or `record struct` with `init` properties over classes
  with public setters. Use `with` expressions instead of in-place mutation.
- Model sum types as sealed hierarchies and match on them with pattern
  matching.
- Public API exposes `IReadOnlyList<T>`, `IReadOnlyDictionary<TK,TV>`, or
  `ImmutableArray<T>` unless callers need to mutate.
- Flag service classes that own mutable state the caller did not ask for,
  and mutable singletons without an explicit invalidation story.
- Parse controller inputs into typed domain values once, and let downstream
  code trust them.
- `DateTime.Now` in domain logic is a finding. Inject the clock.

## Tooling

- A new project without `<Nullable>enable</Nullable>` or
  `<TreatWarningsAsErrors>true</TreatWarningsAsErrors>` is a finding.
- In any project, new warnings block unless an EditorConfig change in the
  same diff shifts the rule and says why.

## Checks

- Each null-forgiving `!` without a comment saying why the value cannot be
  null is a finding.
- A generic `Exception` or `InvalidOperationException` for an expected domain
  outcome is a finding. Use a named exception type or a result variant.
- The compiler (CS8509) only demands a discard arm, so a `switch` over a
  closed hierarchy still compiles after a new subtype is added. When the diff
  adds a subtype, check every `switch` over the hierarchy. Discard arms
  should throw, not return a default.
- Secrets in checked-in `appsettings*.json` are a finding.
