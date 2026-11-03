# Python review reference

Use when reviewing Python code in the diff. Apply version-gated advice only
when the repo's `requires-python` allows it.

## Domain-modeling bias

Route deeper modeling questions to `domain-modeling`.

- Prefer `@dataclass(frozen=True, slots=True, kw_only=True)` value objects.
  Use a plain class only when behavior truly belongs with the data.
- Prefer pure functions over methods that mutate `self`. A class that exists
  only as a namespace for functions is a smell.
- Parse at the boundary with Pydantic or `attrs`. Do not pass those models
  through internal layers, because each construction re-runs validation.
- Keep effects (DB, HTTP, filesystem) at module edges. Import-time I/O is a
  finding.
- Model closed sets and distinct identities with `StrEnum`, `Literal`, and
  `NewType`.
- Money is never a `float`: use `Decimal` or integer cents. See
  `domain-modeling` Rule 8.

## Tooling

- A missing strict mypy or pyright setup is not a finding unless the diff
  adds or weakens the type-checking contract.
- Security and dependency tools (Bandit or Ruff `S`, `pip-audit`, secret
  scanning) produce findings when present and failing, or when a high-risk
  diff has no guard at all.
- New tests use spec-style structure (`pytest-describe` or behavior-named
  tests), following an existing suite's style.
- Do not file Ruff-migration findings on a repo that uses Black, isort, or
  Flake8.
- New Python packaging uses `uv`. Existing repos keep their package manager.

## Type system

- `dict[str, Any]` past a deserialization boundary should be a `TypedDict`
  or a dataclass.
- `# type: ignore` without an error code blocks.
- `Any` needs a comment saying why. Prefer `object` when any value is fine,
  because it forces narrowing.
- Prefer `Protocol` over `ABC` for structural consumers.
  `@runtime_checkable` checks only that attributes exist, not their
  signatures.
- Decorators use `ParamSpec` and `Concatenate`, not `Callable[..., T]`.
- Parameters accept `Iterable`, `Mapping`, or `Sequence`. Returns are
  concrete, such as `list[T]`, so callers can iterate twice.
- An `Optional[T]` or `T | None` return that never returns `None` is a
  finding.

## Error handling

- Expected domain failures use named exception classes or typed result
  variants, not `Exception("message")` or `RuntimeError("message")`.
- `except Exception:` is acceptable only at trust boundaries: a request
  handler, the top-level CLI, or a supervisor.
- Log or re-raise, never both. `log.error(...); raise` double-logs at the
  boundary. Use `log.exception(...)` when handling, or a bare `raise` when
  propagating.
- Changing `raise X` to `raise ExceptionGroup(...)` breaks callers'
  `except X` and is a breaking change.

## Async

- `asyncio.gather` does not cancel siblings when one fails, so they orphan.
  `return_exceptions=True` turns failures into return values that callers
  forget to inspect.
- `httpx.AsyncClient`, `aiohttp.ClientSession`, and asyncpg pools bind to the
  event loop that created them. A module-level cached instance is a finding.

## Security

- After `(BASE / name).resolve()`, check `target.is_relative_to(BASE)`.
  Joining paths alone does not stop traversal.
- JWT decoding pins `algorithms=[...]` and validates `iss`, `aud`, `exp`,
  and `nbf`. Accepting the header's algorithm allows `alg: none` and key
  confusion.
- Passwords use `argon2-cffi` or `bcrypt`, never a salted SHA.
- Untrusted XML goes through `defusedxml`. Secrets in settings use
  `pydantic.SecretStr` so `repr` masks them.
- GitHub Actions are pinned to commit SHAs, not tags.

## Metrics

- Metric labels stay bounded. A `user_id` or request id as a label is a
  finding.

## API and signature design

- Booleans and optional parameters are keyword-only. New parameters go
  after `*,` so existing positional calls keep working.
- `**kwargs` on a public surface silently accepts typos. Use explicit
  parameters, a `TypedDict`, or `ParamSpec` for real passthrough.
- The public surface is what `__all__` and the top-level package export.
- Deprecation warnings pass `stacklevel=2` so they blame the caller.
