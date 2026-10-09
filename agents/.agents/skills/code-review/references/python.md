# Python review reference

Use when reviewing Python code in the diff. Apply this alongside the
main `code-review` skill workflow. Before using any version-specific
guidance, read the repo's declared Python support from `pyproject.toml`,
`setup.cfg`, classifiers, CI, Docker images, and README. Repo compatibility
wins: Python 3.8 libraries do not get Python 3.10+ syntax findings.

## Domain-modeling bias (apply first)

Even though Python supports OOP, the `domain-modeling` skill's doctrine
is canonical:

- Prefer `@dataclass(frozen=True, slots=True, kw_only=True)` value
  objects internally; reach for plain classes only when behavior
  genuinely belongs with data.
- Pure functions over methods that mutate `self`. A class that exists
  only as a namespace for free functions is a smell: flag it.
- Parse at the boundary with Pydantic v2 / `attrs`; emit DTOs on the
  way out. Don't pass Pydantic models through ten layers: the
  per-construction validation is a 2–3× tax on internal hot paths.
- Push side effects (DB, HTTP, filesystem) to module edges; keep
  domain logic pure and testable without mocks.
- Make illegal states unrepresentable: `StrEnum`, `Literal`, sealed
  dataclass hierarchies, `NewType` for distinct identities.

When in doubt, route to the `domain-modeling` skill.

## Tooling that should be passing

- Run the repo's declared checks first. If it uses Ruff, prefer
  `ruff check` and `ruff format --check`; if it uses Black/isort/Flake8,
  treat those as the current contract unless the diff is changing tooling.
- Type checking is valuable, but match the repo's checker and strictness
  level. Missing strict mypy/pyright is not a review finding unless the change
  adds or weakens the type-checking contract.
- `pytest` is the default behavior-focused runner when the repo has no other
  convention. Prefer spec/behavior structure (`describe`/`it` via
  `pytest-describe`, or clear test names) when adding tests, but follow an
  existing suite's style.
- Security and dependency checks should match the repo's risk surface and
  existing tooling: Bandit/Ruff `S`, `pip-audit`/OSV, and secret scanning are
  findings when present and failing, or when a high-risk diff lacks any guard.
- Packaging advice is conditional. Use `uv` when the repo has chosen it or is
  adding Python tooling from scratch; otherwise respect the existing supported
  package manager and lockfile.

## Type system

- Modern syntax follows declared support. On Python 3.10+ projects, prefer
  `list[T]`, `dict[K, V]`, `X | None`. On Python 3.8/3.9-compatible projects,
  `typing.List`, `typing.Dict`, `Optional`, and `Union` may be required unless
  `from __future__ import annotations` and the project's tooling support the
  newer form.
- `dict[str, Any]` is a `TypedDict` waiting to be born. The
  single most common type smell: flag it on sight.
- `# type: ignore` without an error code → block.
- `Any` silently disables checking on the value and everything
  derived from it. Prefer `object` when you mean "I don't care"; it
  forces narrowing.
- `Protocol` (structural) over `ABC` (nominal) for "anything with
  `.read()`"-style consumers. `@runtime_checkable` only checks
  attribute *presence*, not signatures.
- `TypeIs` (3.13+) narrows both branches; `TypeGuard` only narrows
  true. Use it only when the supported runtime or `typing_extensions` allows it.
- `@override` (3.12+ / `typing_extensions`) on overriding methods when the repo
  has enabled that convention.
- `Self` (3.11+ / `typing_extensions`) for fluent return types: replaces
  `T = TypeVar("T", bound="MyClass")`.
- Decorators: `ParamSpec`/`Concatenate` (PEP 612), never
  `Callable[..., T]`.
- PEP 695 generic syntax (3.12+): `class Stack[T]:` over the old
  `TypeVar` dance only in projects that have dropped older runtime support.
- Liberal in (`Iterable`, `Mapping`, `Sequence` parameters), strict
  out (concrete `list[T]` returns so callers can iterate twice).

## Error handling

- Expected failures use specific exception classes or typed
  `Result`/variant shapes. `raise "message"` is invalid Python, but
  `raise Exception("message")` or `raise RuntimeError("message")` for
  domain outcomes is still a finding; define a named domain error or
  return a typed result.
- Bare `except:` catches `BaseException` (`KeyboardInterrupt`,
  `SystemExit`, `asyncio.CancelledError`). Never acceptable.
  `except Exception:` is acceptable only at trust boundaries
  (request handler, top-level CLI, supervisor).
- `raise X from e` to preserve the chain; `from None` only when
  deliberately hiding implementation detail; bare `raise` to
  re-raise the original. `raise X(...)` inside `except` already
  chains via `__context__`: don't accidentally suppress.
- Log-and-reraise is an antipattern: `log.error(f"... {e}"); raise`
  writes a log line with no traceback (the bare `raise` keeps it),
  then the boundary logs the same error again. Either
  `log.exception("foo failed")` (full traceback, no re-raise) or
  re-raise, never both.
- `ExceptionGroup` / `except*` (PEP 654, 3.11+) for aggregated
  validation, `TaskGroup` failures, parallel cleanup. Migrating
  from `raise X` to `raise ExceptionGroup` is a breaking change.
- `contextlib.suppress(SpecificError)` is fine for narrow
  idempotency (`suppress(FileNotFoundError): path.unlink()`); never
  `suppress(Exception)`.
- `assert` for runtime validation in production is **stripped under
  `python -O`**. Fine in tests and for type-narrowing hints; never
  for input validation or security checks.
- Never catch `asyncio.CancelledError` without re-raising: it
  breaks the cancellation contract (it's `BaseException` since 3.8).

## Async / concurrency

- Blocking I/O in `async def` is the #1 production incident.
  `requests.get`, `time.sleep`, `open().read()` block the loop for
  the whole RTT. Use `httpx.AsyncClient`, `await asyncio.sleep`,
  `await asyncio.to_thread(...)`.
- `asyncio.TaskGroup` (3.11+) over `gather()` for new code.
  `gather` does NOT cancel siblings on first failure: they orphan.
  `gather(..., return_exceptions=True)` silently turns failures
  into result objects easy to forget to inspect.
- `async with asyncio.timeout(5):` over `wait_for(..., timeout=5)`.
- `asyncio.create_task(coro)` only stores a weak reference;
  fire-and-forget tasks vanish (Ruff `RUF006`). Either own them in
  a `TaskGroup` or hold a strong ref.
- `httpx.AsyncClient` / `aiohttp.ClientSession` / asyncpg pools
  bind to the loop they were created on; never cache one at module
  level. Fresh `httpx.AsyncClient()` per request is a TLS-handshake
  smell.
- `asyncio` with CPU-bound work isn't concurrency. Move to
  `to_thread`/`ProcessPoolExecutor`.
- Threads: shared mutable state needs `Lock` / `RLock` /
  `concurrent` collections, never plain `dict`. `multiprocessing`
  entry point must be guarded with `if __name__ == "__main__":`.

## Resources and performance

- `with` (or `async with`) on every `Closeable`. `open(path).read()`
  leaks the fd if `.read()` raises (Ruff `SIM115`).
  `Path.read_text()` for the one-liner.
- `pathlib` over `os.path` in new code (Ruff `PTH`).
- `lru_cache` / `functools.cache` on instance methods leaks because
  the cache holds `self`. Use `functools.cached_property` (requires
  `__dict__`, won't work on `slots=True` without an explicit slot).
- Generators / generator expressions for large iterables;
  comprehensions only when readable in ~2 lines.
- Float `==` is wrong; use `math.isclose(a, b, rel_tol=...)`. Money
  uses `Decimal` or integer cents, never `float`. See
  `domain-modeling/references/money.md` for the cross-language discipline
  (currency travels with amount, ISO 4217, per-currency decimals).
- `dataclass(slots=True)` cuts memory ~40% and speeds attribute
  access; `frozen=True` for value objects (avoid on hot paths,
  ~2.4× slower instantiation).
- Timezone-aware datetimes only in production code (Ruff `DTZ`).
  `datetime.now(tz=UTC)`, never naive `datetime.now()`. See
  `domain-modeling/references/dates.md` for the cross-language discipline
  (UTC storage, RFC 3339 on the wire, instant vs wall-clock-only).

## Security

- SQL injection: every value derived from user input must use
  bind parameters. `cur.execute(f"... {x}")` and
  `text(f"... {x}")` are Critical even when `x` looks "validated".
- Command injection: `subprocess.run([cmd, *args])` always;
  `shell=True` with non-literal command is Critical (Bandit `B602`).
- `pickle` deserialisation of untrusted data is RCE by design. Use
  `json`, `msgpack(strict_map_key=True, raw=False)`, or Pydantic.
  `ast.literal_eval` for "evaluate this Python literal."
- Path traversal: `os.path.join('/uploads', '../etc/passwd')` walks
  out happily. After `(BASE / name).resolve()`, check
  `target.is_relative_to(BASE)`.
- `secrets.token_urlsafe(n)` for tokens; **never `random.*`** for
  security. `hmac.compare_digest` for token comparisons. Passwords:
  `argon2-cffi` or `bcrypt`. Never raw SHA + salt; never MD5/SHA-1
  for security.
- `requests` / `httpx` calls without `timeout=` hang forever: a
  finding in any service path.
- `verify=False` is Critical in production HTTP. `yaml.safe_load`
  always; never `yaml.load`. `defusedxml` for untrusted XML. JWT:
  reject `alg: none`; specify `algorithms=["RS256"]` (the RS256/HMAC
  confusion attack uses the public key as the HMAC secret); validate
  `iss`, `aud`, `exp`, `nbf`.
- Secrets in code: gitleaks / `detect-secrets` pre-commit; wrap with
  `pydantic.SecretStr` so `repr` masks them.
- Dependencies: `uv lock` with hashes; `pip-audit` / `osv-scanner`
  in CI; pin GitHub Actions to commit SHAs (not tags).

## Logging and observability

- `print()` in libraries or services is a finding (Ruff `T20`).
  Use `logging` (or `structlog`).
- `logger.info("user %s did %s", uid, action)`: lazy `%` args.
  f-strings inside log calls interpolate eagerly even when the
  level is filtered (Ruff `G004` is correct but pedantic; many
  ignore for non-hot paths). With `structlog` the question is moot.
- `logger.exception("payment_failed", order_id=...)` inside the
  `except`. Never log secrets, tokens, PII, full request/response
  bodies, `Authorization` headers: redact at the processor level.
- Libraries add a `NullHandler` and never call `basicConfig` (which
  mutates the root logger).
- Metrics label cardinality: `user_id` as a Prometheus label blows
  up the TSDB. Bound by what's measured.

## API and signature design

- Keyword-only after ~2 args, especially booleans and anything
  optional (`def fn(x, /, *, force=False, dry_run=False):`). Two
  positional booleans is a perpetual bug factory. The only safe
  place to add a new parameter is after `*,`.
- Mutable defaults: `def f(xs=[])` shares one list across calls.
  Use `field(default_factory=list)` in dataclasses or the
  `_MISSING = object()` sentinel pattern when `None` is itself
  valid. Always compare sentinels with `is`.
- Stringly-typed parameters → `StrEnum` (3.11+) or `Literal[...]`.
- `**kwargs` on a public surface silently swallows typos; use
  explicit args or a `TypedDict`. `ParamSpec` for legitimate
  passthrough.
- Public/private: leading underscore + `__all__` + explicit
  `from .impl import X as X` re-export. Anything not exported from
  the top-level package is not public.
- Deprecation: `@deprecated("Use Client.fetch instead; removed in
  v3.0 (2026-Q4).")` (3.13+ / `typing_extensions`). Pre-3.13:
  `warnings.warn(..., DeprecationWarning, stacklevel=2)`:
  `stacklevel=2` is critical so the warning blames the caller.
  Always document the removal version.

## Anti-patterns / red flags

- `def fn(values=[])`: mutable default.
- `except:` or `except Exception:` outside a trust boundary.
- `except Exception as e: log.error(f"... {e}"); raise`: log-and-reraise.
- `except asyncio.CancelledError: pass`: breaks cancellation contract.
- `raise X(...)` inside `except` without `from e` (or bare `raise`).
- `# type: ignore` without an error code; `Any` without a comment.
- `dict[str, Any]` past a deserialisation boundary.
- `Optional[T]` returns that never return `None`. `Optional` syntax itself is
  only a finding when the repo's declared Python version and style allow
  `T | None`.
- `print(...)` for logging in production code.
- `time.sleep(n)` or `requests.get(...)` inside `async def`.
- `asyncio.create_task(coro)` with no strong ref or TaskGroup.
- `asyncio.gather(...)` where TaskGroup semantics are wanted.
- `eval`, `exec`, `pickle.loads` on anything from outside.
- `subprocess(..., shell=True)` with a non-literal command.
- `cur.execute(f"... {x}")` or `text(f"... {x}")`: string-built SQL.
- `requests` / `httpx` without `timeout=`.
- `verify=False` for TLS in production.
- `yaml.load(...)` instead of `yaml.safe_load`.
- `random.random()` / `random.choice()` for anything security-sensitive.
- `assert` for input validation, security checks, or auth gates.
- `if x is "admin"` / `if x == None`: `is` only for sentinels;
  `is None` mandatory.
- `type(x) == list`: use `isinstance` (or `Protocol`).
- `lambda` assigned to a name (Ruff `E731`).
- `0.1 + 0.2 == 0.3`: float `==`; use `math.isclose` / `Decimal`.
- `os.path.join(...)` in new code.
- `utils.py` / `helpers.py` / `*Manager` / `*Service` with no real
  noun.
- Top-level I/O on import; `logging.basicConfig` in library code.
- Pydantic models passed through ten internal layers.

## Sources

- Ruff rule index: <https://docs.astral.sh/ruff/rules/>
- mypy strict mode:
  <https://mypy.readthedocs.io/en/stable/command_line.html#cmdoption-mypy-strict>
- PEP 604 (`X | Y` unions), PEP 585 (builtin generics), PEP 612
  (`ParamSpec`), PEP 654 (`ExceptionGroup`), PEP 695 (generic
  syntax), PEP 702 (`@deprecated`), PEP 735 (dependency groups),
  PEP 742 (`TypeIs`).
- asyncio gotchas:
  <https://docs.python.org/3/library/asyncio-dev.html>
- `asyncio.TaskGroup`:
  <https://docs.python.org/3/library/asyncio-task.html#task-groups>
- Bandit rule index:
  <https://bandit.readthedocs.io/en/latest/plugins/index.html>
- OWASP ASVS Python guidance:
  <https://cheatsheetseries.owasp.org/cheatsheets/SQL_Injection_Prevention_Cheat_Sheet.html>
- structlog:
  <https://www.structlog.org/en/stable/>
- uv: <https://docs.astral.sh/uv/>
