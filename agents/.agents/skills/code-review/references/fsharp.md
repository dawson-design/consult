# F# review reference

Use when reviewing F# code in the diff.

## Domain-modeling bias

F# code often carries C# habits into the domain. Route deeper modeling
questions to `domain-modeling`.

- Prefer records and discriminated unions over classes. Classes belong at
  I/O or interop boundaries.
- A DU with the valid cases beats a record of optional fields plus an
  `IsValid` flag.
- Domain logic returns `Result`. Effects stay at the edge. Parse DTOs into
  domain types once.
- `let mutable` and `ref` cells belong only in edge caches and adapters.
- C# interop goes through a thin adapter module that maps null to `Option`.

## Tooling

- New compiler warnings block unless an EditorConfig change in the same diff
  shifts the rule and says why.

## Checks

- A new `failwith`, `raise`, or `invalidArg` in domain code needs a stated
  precondition the types cannot yet express. Partial active patterns return
  `None` instead of throwing.
- `Result.iter` or `|> ignore` that discards a meaningful `Error` is a
  finding.
- A new custom computation expression builder needs a reason in the diff.
- Wrapping synchronous functions in `task { return ... }` adds allocations
  for no benefit.
