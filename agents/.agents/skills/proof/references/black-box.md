# Black-Box Tests

Load this reference when choosing a test's inputs or expected outputs, or
when writing a black-box or integration test, a golden file, or the
regression guard for a fixed bug.

## Rule

A black-box test gives the code a fixed input at the outermost boundary its
caller uses and checks the whole output. It keeps passing when the internals
are rewritten and fails when the behavior changes. Two properties matter
more than test level: the cases and expected values come from outside the
code, and the agent changing the code does not edit the tests to make them
pass.

## Where tests enter

- A test of a function through its signature is black-box only when the
  function is a public API that code outside the project calls, such as a
  library's exported parser. The same test against an internal function is
  a unit test.
- When a page only displays what an HTTP API returns, put those cases at
  the API. Keep browser tests for the journeys users depend on and for
  behavior only the page has. Find elements by role, label, or visible text,
  because CSS classes and DOM structure are internals.

## Take cases and expected outputs from outside the code

- Read expected outputs from the request, the issue, the spec, an example
  the user gave, or a reference such as a schema or protocol document. When
  no source states one, write it down before running the code and say where
  it came from.
- For a rewrite or migration, the old program is the oracle. Run old and new
  on the same inputs and compare outputs.
- An expected value copied from the code's own output only pins current
  behavior. Use one before a refactor, and never report it as proof the
  behavior is right.
- Take the cases from the spec, not the code, because a test read from the
  code cannot find a case the code leaves out. Cover independent settings
  such as browser, locale, and feature flags pairwise; cover every
  three-way combination only when a failure would be costly.
- Write the cases as a table of input and expected output, add real inputs
  that have broken before, and match each acceptance criterion to its cases.
  A criterion with no case is unproven.
- When the host can run a second agent, have one context write the tests
  from the spec and another write the code.
- When the spec states a rule rather than examples, use a property test.
  When no source gives the exact output, check how related inputs' outputs
  relate (a metamorphic test).

## Keep the tests out of the agent's reach

- When a test contradicts the spec or the request, stop and report the
  conflict instead of making the test pass.
- Check the diff for code that branches on a test's literal inputs or
  redefines equality. Read-only tests stop test edits but not this.
- A test-repair tool's patch is a test edit. Accept a locator fix only when
  the old locator targeted internals and the new one finds the same element
  by role, label, or text, and report it. A changed role, label, or text is
  a behavior change the user approves first. Reject a patch that changes
  what an assertion checks or marks the test skipped.
- Run the full suite in CI on the branch, so a test the agent did not run
  still guards the merge.

## Make the output repeatable and assert all of it

- Replace values that differ on every run, such as temp paths, with named
  placeholders, and sort collections the contract does not order.
- When the code calls a model, fake the model at the system edge with
  recorded responses, and assert the code's output for valid and invalid
  responses. A live model's pass rate over fixed cases, against a threshold
  the user sets, is an eval: run it outside the suite and report it as one.
- For HTTP, assert the status, the body, and the headers the client reads.
  For a CLI, assert the exit code, stdout, stderr, and files written. For a
  state change, read the state back through the public boundary or the real
  store.
- Prefer exact equality to "contains", which lets new fields, extra rows,
  and changed messages through.

## Golden files

- Store a large expected output (a report, a generated file, a full API
  response) in a file next to the test, one small file per scenario.
- Commit the golden file and review its diff like code.
- Regenerate it only for a behavior change the user approved, and review the
  diff before committing.
- A golden file checks a program's output for an input. `proof` Rule 7's
  ban on asserting literal text covers config and docs.

## Regression guards and integration tests

- Reproduce a bug at the outermost boundary that shows it, with the input
  from the report. Use an integration test when the bug needs a real
  dependency, and a unit test when it is in pure domain logic or nothing
  else reproduces it. Name the test after the behavior and link the issue.
- Integration tests run the real dependency, such as a database in a
  container, not a mock of its client, because a mocked client cannot show
  that a query or message works. Keep each one on the adapter: queries,
  constraints, transactions, serialization, and wire formats.
- An agent clicking through a running app is exploration, not proof. Turn
  each finding worth keeping into a scripted test whose result needs no
  agent to judge, and cite that test as the evidence.
