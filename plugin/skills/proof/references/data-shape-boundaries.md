# Data-shape boundaries: worked examples

This reference expands `proof` Rule 3, prefer black-box tests at boundaries.
The shared rule across all examples: **a boundary worth testing is a point
where data shape or values change observably**. These shape-change points
are component handoffs: the seams where production defects concentrate.
"Boundary" and "handoff" are used interchangeably here. HTTP, CLI, UI, and
module facades are special cases of this: the shape change is "internal
value -> external representation". Pipeline seams, parser edges, validator
outputs, middleware boundaries, and sans-IO byte surfaces are the same kind
of thing.

Rule 3 puts the tests at the outermost boundary the caller uses. The seams
inside show which cases those tests must cover: one case for each way the
data can change shape at each seam. A seam gets tests of its own only when it
is itself a public surface, or to guard a fixed bug.

Test placement is also a code-organization signal. If a clean seam test is
hard to write, the seam is wrong: simplify the code before piling on mocks.

For each pattern below: the seam set, what to assert at the success
envelope, what to assert at the error envelope, where the user-facing error
*content* lives, when to test an internal stage on its own, and the
anti-pattern that signals over-testing or tangle. Under Rule 3, a test of
an internal stage on its own guards a fixed bug that the outer tests cannot
reproduce. A stage that is a public surface gets a black-box test at that
surface instead.

## Pattern 1: ETL pipeline (extract, transform, load)

**Seams:** extract output -> transform input; transform output -> load
input; load output -> destination state.

**Success-shape assertions:** run the pipeline from a fixed source and
assert the destination state: row count, per-record shape (field names,
types, key invariants), and the values produced from known inputs. Pick
source rows that exercise each seam: the extract contract, each transform
branch, and each load constraint.

**Error-shape assertions:** from a source that is unreachable, malformed, or
empty, assert what the runner reports. Feed records the transform cannot map
and assert where they land, such as a dead-letter destination or a typed
`TransformError` in the run report. Load rows that violate a constraint and
assert the partial-write and rollback behavior in the destination.

**User-facing error content:** if the pipeline is exposed via a runner that
reports to a human or upstream system, assert the failure summary that
runner produces (exit code, structured error log, dead-letter destination),
not just that an exception was raised somewhere internal.

**Test an internal stage on its own when:** a fixed bug lives in that stage
and no pipeline run reproduces it. A stage with many branches or accumulated
state (windowed aggregations, dedup, joins) gets more source cases through
the pipeline run, not tests of its own.

**Anti-pattern:** one unit test per pure mapping function. The pipeline runs
already exercise these.

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

**Test an internal stage on its own when:** a sub-parser is a public surface
of its own, such as an expression parser the library exports. Test it
black-box at that surface. Otherwise, test one rule on its own only
to guard a fixed bug that no top-level input reproduces.

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

**Test an internal stage on its own when:** a fixed bug lives in one coercion
or cross-field rule and the public-shape tests cannot reproduce it. For a
rule with many branches, write property-based tests over invariants at the
validator output instead of per-rule tests.

**Anti-pattern:** one unit test per field validator predicate. The validator
output already proves them.

## Pattern 4: Middleware chain (request -> handler)

**Seams:** request -> middleware-1 output -> middleware-2 output -> ... ->
handler input -> handler output -> response.

**Success-shape assertions:** at the response. If middleware enriches the
request (auth context, parsed body, correlation ID), assert the effect the
client sees, such as the response body or headers, or a captured log line.
Do not assert the handler's input, which is internal to the chain.

**Error-shape assertions:** at each seam where the chain can short-circuit
(auth failure, rate limit, body too large, validation failure). Assert the
HTTP status, the error body shape, and the message a consumer can act on.

**User-facing error content:** a 401 with body `{"error": "unauthenticated"}`
is a different proof than a 401 with body
`{"code": "TOKEN_EXPIRED", "message": "Sign in again to continue"}`. The
consumer-actionable form is the value claim.

**Test an internal stage on its own when:** a fixed bug lives in one
middleware (e.g. token refresh around an expiry time) and the chain tests
cannot reproduce it. Pin the clock at the system edge first. That lets the
chain test reach most such cases.

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

**Test an internal stage on its own when:** an inner state machine is a
public library of its own (e.g. a TLS handshake library inside a higher
protocol). Test it black-box at its own public surface (bytes-in /
bytes-out), not at the call graph level.

**Anti-pattern:** mocking sockets and asserting `socket.send()` was called
with specific bytes. The mock is the test; the test proves nothing about
the protocol's actual behavior.

## Pattern 6: Functional core, imperative shell

**Seams:** shell input (HTTP request, CLI args, file read) -> core input
(values); core output (values, including `Result.Err`) -> shell action
(write, send, render).

**Success-shape assertions:** feed the table of representative cases
through the shell, such as an in-process HTTP request or a CLI call, and
assert the output. A thin shell keeps these tests fast: call it in process
and pin the clock and other system edges.

**Error-shape assertions:** feed the shell inputs that should produce a core
`Result.Err`, and assert the user-facing error: HTTP status, CLI exit code,
error message.

**User-facing error content:** the shell is where the message reaches the
user. Assert the translated form there. The core names the error case and
the shell renders it, so one assertion at the shell proves both.

**Test an internal stage on its own when:** the core is a published API that
code outside the project calls, or a fixed bug lives in one core function
and no shell input reproduces it. Algorithmic code (sorting, pathfinding,
dedup) gets its table of cases through the shell.

**Anti-pattern:** one test per core function with a single shell smoke test.
The core tests pin internal signatures that the next rewrite changes, and the
smoke test leaves most behavior unproven at the boundary callers use.

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
