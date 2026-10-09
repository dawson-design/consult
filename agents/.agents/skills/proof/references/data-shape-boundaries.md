# Data-shape boundaries: worked examples

This reference expands `proof` Rule 3, test at boundaries. The shared rule across all
examples: **a boundary worth testing is a point where data shape or values
change observably**. These shape-change points are component handoffs: the
seams where production defects concentrate, and the primary proof target.
"Boundary" and "handoff" are used interchangeably here. HTTP, CLI, UI, and
module facades are special cases of this: the shape change is "internal
value -> external representation". Pipeline seams, parser edges, validator
outputs, middleware boundaries, and sans-IO byte surfaces are the same kind
of thing.

Test placement is also a code-organization signal. If a clean seam test is
hard to write, the seam is wrong: simplify the code before piling on mocks.

For each pattern below: the seam set, what to assert at the success
envelope, what to assert at the error envelope, where the user-facing error
*content* lives, when an internal-stage test is genuinely warranted, and the
anti-pattern that signals over-testing or tangle.

## Pattern 1: ETL pipeline (extract, transform, load)

**Seams:** extract output -> transform input; transform output -> load
input; load output -> destination state.

**Success-shape assertions:** at extract output, assert row count and schema
match the source contract. At transform output, assert the per-record shape
(field names, types, key invariants) and representative values produced from
known inputs. At load output, assert the destination row count and content
match the transformed shape.

**Error-shape assertions:** at extract, assert the error envelope when the
source is unreachable, malformed, or empty. At transform, assert the error
envelope for unmappable records (e.g. dropped to a dead-letter shape, or
surfaced as a typed `TransformError`). At load, assert the error envelope for
constraint violations, partial writes, and rollback semantics.

**User-facing error content:** if the pipeline is exposed via a runner that
reports to a human or upstream system, assert the failure summary that
runner produces (exit code, structured error log, dead-letter destination),
not just that an exception was raised somewhere internal.

**Internal-stage test warranted when:** a transform stage has non-trivial
branching (multiple output shapes per input) or accumulates state (windowed
aggregations, dedup, joins). Then test that stage in isolation against its
contract, separately from the seam tests.

**Anti-pattern:** one unit test per pure mapping function. The seam tests
above and below already exercise these.

## Pattern 2: Parser (raw -> AST)

**Seams:** input bytes/string -> parse result (AST or `ParseError`).

**Success-shape assertions:** at the parse boundary, assert the AST shape
for representative valid inputs (one per grammar production worth caring
about). One test per shape, not one per internal rule function.

**Error-shape assertions:** at the same boundary, assert the `ParseError`
shape (error kind, position, message) for representative invalid inputs.
Cover at least: unexpected token, unterminated construct, ambiguous input
(if rejected), and EOF in the middle of a production.

**User-facing error content:** assert the message text users will see
(`"Unexpected '}' at line 4, column 12"`), not just `expect(parse).toThrow()`.
A parser whose error messages are unhelpful is parser whose error contract is
unproven.

**Internal-stage test warranted when:** the parser composes sub-parsers that
are independently reusable (e.g. an expression parser used by both a script
mode and a REPL mode), or when one rule has subtle backtracking behavior the
top-level tests cannot drive deterministically.

**Anti-pattern:** unit tests per parser combinator function. They duplicate
the seam coverage and break on internal refactors that preserve the public
grammar.

## Pattern 3: Validator (raw input -> typed structure)

**Seams:** raw input (request body, form data, untyped object) -> validated
typed structure or `ValidationError`.

**Success-shape assertions:** at the validator output, assert the typed
shape for canonical valid inputs. Cover the boundary cases of the type
system the validator promises to enforce (trimmed strings, normalized
emails, parsed dates, coerced enums).

**Error-shape assertions:** at the same seam, assert the `ValidationError`
envelope, typically per-field messages keyed by path. Cover: missing
required, type mismatch, format violation, cross-field invariants.

**User-facing error content:** for each user-correctable failure, assert
the exact message the consumer will see. `"Email is required"` is a different
test from `"Email format is invalid"`, and both are different from
`"Validation failed"`. The point of validation is that the user can fix the
input; that's a value claim at the seam.

**Internal-stage test warranted when:** a non-trivial coercion or
cross-field rule has many branches that the public-shape tests cannot
all express compactly. Property-based testing over invariants often beats
hand-rolled per-rule tests in this case.

**Anti-pattern:** one unit test per field validator predicate. The validator
output already proves them.

## Pattern 4: Middleware chain (request -> handler)

**Seams:** request -> middleware-1 output -> middleware-2 output -> ... ->
handler input -> handler output -> response.

**Success-shape assertions:** at each shape change. If middleware enriches
the request (auth context, parsed body, correlation ID), assert the enriched
shape at the boundary it emerges from. The handler's input is itself a
seam: assert what the handler sees, not what was sent over the wire.

**Error-shape assertions:** at each seam where the chain can short-circuit
(auth failure, rate limit, body too large, validation failure). Assert the
HTTP status, the error body shape, and the message a consumer can act on.

**User-facing error content:** a 401 with body `{"error": "unauthenticated"}`
is a different proof than a 401 with body
`{"code": "TOKEN_EXPIRED", "message": "Sign in again to continue"}`. The
consumer-actionable form is the value claim.

**Internal-stage test warranted when:** a middleware has non-trivial logic
in isolation (e.g. token refresh with a clock dependency) and the chain
tests cannot drive its edge cases compactly.

**Anti-pattern:** one assertion per middleware execution, in order, on every
chain test. Test once per shape change, not once per call.

## Pattern 5: Sans-IO protocol (bytes-in / bytes-out)

**Seams:** bytes received -> protocol state transition -> bytes to send,
all behind a synchronous public surface that performs no I/O.

**Success-shape assertions:** push canonical byte sequences in, assert the
state transitions and outbound byte sequences. The test does not mock
sockets, time, or the network; the protocol library is a pure transform
and is tested as one.

**Error-shape assertions:** push malformed or out-of-order byte sequences
in, assert the protocol-error byte sequence emitted (or the state machine's
explicit `ProtocolError` value).

**User-facing error content:** for protocols where errors surface to a
calling application (e.g. an HTTP-style error frame), assert the frame's
structured fields. For protocols where errors close the connection, assert
the closing frame and reason code.

**Internal-stage test warranted when:** sub-state machines compose (e.g. a
TLS handshake state machine inside a higher protocol). Test the inner state
machine at its own public surface (bytes-in / bytes-out), not at the call
graph level.

**Anti-pattern:** mocking sockets and asserting `socket.send()` was called
with specific bytes. The mock is the test; the test proves nothing about
the protocol's actual behavior.

## Pattern 6: Functional core, imperative shell

**Seams:** shell input (HTTP request, CLI args, file read) -> core input
(values); core output (values, including `Result.Err`) -> shell action
(write, send, render).

**Success-shape assertions:** in the core, push representative values in,
assert the value out. Many tests, fast, no mocks. At the shell, one or two
integration tests per externally-observable behavior (HTTP endpoint
returns expected response; CLI command writes expected file).

**Error-shape assertions:** in the core, push values that should produce
`Result.Err`, assert the error variant and its content. At the shell, assert
that a core `Result.Err` becomes the right user-facing error: HTTP status,
CLI exit code, error message.

**User-facing error content:** the shell is where the message reaches the
user. Assert the translated form there. The core's job is to name the error
case; the shell's job is to render it; both seams need their own assertions.

**Internal-stage test warranted when:** a core function has algorithmic
complexity worth testing as a unit (sorting, pathfinding, dedup); even
then, prefer testing it through the public function that uses it, unless
that function obscures the cases.

**Anti-pattern:** integration tests for everything. The core is fast and
deterministic; not exploiting that is leaving coverage on the table while
slowing CI.

## Cross-reference: error contracts

The above examples assume the *shape and content* of the error envelope is
already decided. That contract (what fields the error has, how messages
are written for the consumer, what recovery the consumer can take) is owned
by `error-handling`. This skill's job is to ensure the contract is provable
at the seam where the consumer observes it. If the contract is unclear or
inconsistent across seams, hand off to `error-handling` to settle it before
asserting.

## Cross-reference: when seam tests are hard

If a seam test requires many mocks, deep setup, or assertions on internal
call patterns, the seam is wrong, not the test framework. The data and
effects are tangled, the boundary is leaking implementation, or
responsibility is split awkwardly. Hand off to `refactoring` or
`architecture` to simplify the seam first; the proof becomes straightforward
once the design is right. This is `proof`'s most useful diagnostic role:
test placement reveals organization debt that other lenses miss.

## References

The principle that tests belong at points where data shape or values change
is well-supported under several vocabularies in prior writing: boundaries
between functional core and imperative shell, ports and adapters, observable
behavior versus implementation detail, invariants and property-based
testing, sans-IO protocol design, data-oriented programming. The synthesis
under one banner (*data-shape-change is the unifying boundary type, and
test placement is a code-organization signal*) is Consult's framing.

- *Practical Test Pyramid* (Fowler):
  https://martinfowler.com/articles/practical-test-pyramid.html
- *Boundaries* / *Functional Core, Imperative Shell* (Bernhardt):
  https://www.destroyallsoftware.com/talks/boundaries
- *Hexagonal Architecture* (Cockburn):
  https://alistair.cockburn.us/hexagonal-architecture
- *TDD, Where Did It All Go Wrong* (Cooper, NDC 2017):
  https://www.youtube.com/watch?v=EZ05e7EMOLM
- *Unit Testing: Principles, Practices, and Patterns* (Khorikov, Manning,
  2020): https://www.manning.com/books/unit-testing
- *The Magic Tricks of Testing* (Metz, RailsConf 2013):
  https://www.youtube.com/watch?v=URSWYvyc42M
- *How to sans-IO* (Benfield):
  https://sans-io.readthedocs.io/how-to-sans-io.html
- *QuickCheck* (Hughes & Claessen, ICFP 2000):
  https://dl.acm.org/doi/10.1145/351240.351266
- *Beyond Unit Tests* / *Data Invariants* (Wayne):
  https://www.hillelwayne.com/talks/beyond-unit-tests/
- *Data-Oriented Programming* (Sharvit, Manning, 2022):
  https://www.manning.com/books/data-oriented-programming
- *Working Effectively with Legacy Code* (Feathers, 2004); note: Feathers'
  "seam" is a substitution point for testability, related to but distinct
  from "data shape change"; both apply.
