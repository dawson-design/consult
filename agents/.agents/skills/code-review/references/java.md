# Java review reference

Use when reviewing Java code in the diff.

## Domain-modeling bias

Java code often defaults to mutable POJOs. Route deeper modeling questions to
`domain-modeling`.

- Prefer `record` (Java 16+) over POJOs with getters and setters.
- Model sum types as sealed types (Java 17+) with pattern-matching `switch`
  (Java 21+), not downcast chains.
- Public API returns `List.of`, `Map.of`, or unmodifiable views.
- Keep I/O in adapters. Service classes that mutate shared fields after
  construction, and mutable static state, are findings.

## Checks

- New static-analysis warnings in the diff are findings.
  `@SuppressWarnings` needs a reason in a comment.
- Expected domain failures use named exception types or result variants, not
  a generic `RuntimeException("message")`.
- A stateful lambda inside `map` or `filter` is a finding. A parallel stream
  needs a stated reason: CPU-bound work, no shared state, and input large
  enough to pay for the fork-join overhead.
