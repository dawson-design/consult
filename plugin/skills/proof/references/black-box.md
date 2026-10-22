# Black-Box Tests

Load this reference when choosing a test's inputs or expected outputs, or
when writing a black-box or integration test, a golden file, or the
regression guard for a fixed bug.

## Rule

A black-box test gives the code a fixed input at the outermost boundary its
caller uses and checks the whole output. It knows nothing about how the code
computes the result, so it keeps passing when an agent rewrites the
internals and fails when the behavior changes.

Research on agent-written code points at two properties more than at test
level. First, the cases and their expected values must come from outside the
code: a test written by reading the implementation asserts what the code
does, bugs included. Second, the agent changing the code must not be the one
who edits the tests to make them pass. Black-box tests are the simplest way
to meet both, because the request or spec states the cases and outputs a
caller sees. The Canon section lists the studies.

## Tests as experiments

Consult treats acceptance tests as proof, and the method is the scientific
one. The claim under test is that the code maps these inputs to these
outputs, as the spec says. The architecture is the mechanism behind the
claim. Many mechanisms produce the same outputs, so a black-box test checks
the claim without constraining the mechanism, which is why it survives
refactors and rewrites.

The method's rules apply to tests as they stand:

- State the prediction before the observation. The expected output comes
  from the spec before the code runs, never from new code's first output.
- Design the experiment so it can fail. Watch the test fail first when the
  failure is the evidence (`proof` Rule 6), and use mutation testing to check
  that the suite notices broken code.
- Never adjust the results after the fact. Editing a test to make a change
  pass changes the measurement to fit the theory (`proof` Rule 11).
- Treat a passing suite as corroboration, not proof of correctness. The code
  survived every check that could have failed it. One reliable failure
  refutes the claim, and no number of passes rules out a bug.

## Kinds of test

| Kind | Enters at | Use for |
|---|---|---|
| Black-box | The outermost boundary the caller uses: endpoint, CLI, UI, or public API | Every behavior a caller depends on. This is the default. |
| Integration | The code's adapter to a real dependency: database, queue, cache, or another service | Queries, transactions, serialization, and wire formats that only the real dependency can check. |
| Unit | One internal function or class | Only the regression guard for a fixed bug that no black-box or integration test reproduces. |

A test of a function through its signature is black-box only when the
function is a public API that code outside the project calls, such as a
library's exported parser. The same test against an internal function is a
unit test.

When the page only displays what an HTTP API returns, put those cases at the
API, where tests run faster and flake less. Keep browser tests
for the journeys users depend on and for behavior only the page has. Find
elements by role, label, or visible text, because CSS classes and DOM
structure are internals.

Keep the existing tests a change touches, and run them before editing: an
agent told which existing tests cover its change causes far fewer
regressions. Replace a test of internals only with a black-box test of the
same behavior, and say so.

## Take expected outputs from outside the code

- Read the expected output from the request, the issue, the spec, an example
  the user gave, or a reference such as a schema or protocol document.
- For a rewrite or migration, the old program is the oracle. Run old and new
  on the same inputs and compare their outputs.
- When no source states the output, write the expected value before running
  the code, and say where it came from.
- An expected value copied from the code's own output shows only that the
  behavior has not changed. Use one to pin existing behavior before a
  refactor, and report it as that, never as proof the behavior is right.
- When the host can run a second agent, have one context write the
  black-box tests from the spec and another write the code.

## Choose the cases from the spec

The spec sets the inputs as well as the outputs. A test read from the code
exercises only the paths the code has, so it cannot find a case the spec
requires and the code leaves out. Take the cases from the spec with the
standard test design techniques: equivalence partitions (valid and invalid),
boundary values on both sides of each stated limit, decision tables for
business rules, and state transitions, including the ones the spec refuses.
For independent settings such as browser, locale, and feature flags, cover
every pair of values (pairwise testing). Most failures involve only one or
two settings, so pairs are enough unless a failure would be costly. When it
would be, cover every three-way combination.

Write the cases as a table of input and expected output, and add real inputs
that have broken before. Then match each acceptance criterion to the cases
that cover it. A criterion with no case is unproven, and the report says so.

## Keep the tests out of the agent's reach

- An existing test, golden file, or snapshot is the oracle for the change.
  When one fails, the change is wrong or the behavior changed, and only the
  user approves a behavior change.
- Never edit, skip, weaken, or delete a test to make a change pass. That
  includes loosening an assertion, adding a skip marker, or special-casing
  the test input in the code.
- When a test contradicts the spec or the request, stop and report the
  conflict to the user instead of making the test pass. In ImpossibleBench, a
  prompt that said this cut GPT-5's cheating on one task set from 92% to 1%.
- Read-only tests stop test edits but not special-casing, so check the diff
  for code that branches on a test's literal inputs or redefines equality.
- A test-repair tool's patch is a test edit. Accept a locator fix only when
  the old locator targeted internals, such as a CSS class or DOM path, and
  the new one finds the same element by role, label, or text, and report it.
  A changed role, label, or text is a behavior change, so the user approves
  it first. Reject a patch that changes what an assertion checks or marks the
  test skipped, and let the test fail when the element it targets no longer
  exists.
- Run the full suite in CI on the branch, so a test the agent did not run
  still guards the merge.

## Make the output repeatable

The same input has to produce the same output, or the test cannot tell a
regression from noise.

- Pin the clock, random seeds, and generated IDs at the system edge, and pass
  them in as input.
- Sort collections before comparing them when the contract promises no
  order.
- Replace values that differ on every run, such as temp paths, with a fixed
  placeholder in the comparison, and name each one.
- Start each case from fresh state: an empty database, a new temp directory,
  or a seeded fixture.
- When the code calls a model, fake the model at the system edge with
  recorded responses, and assert the code's output for each valid and
  invalid response. Measuring a live model's pass rate over a fixed set of
  cases, against a threshold the user sets, is an eval. Run it outside the
  suite and report it as an eval, not a test.

## Assert the whole output

- For an HTTP call, assert the status, the body, and the headers the client
  reads.
- For a CLI, assert the exit code, stdout, stderr, and any files it writes.
- For a state change, read the state back through the same public boundary
  or from the real store.
- Prefer exact equality to "contains". A partial assertion lets new fields,
  extra rows, and changed messages through. Strengthened tests reject about
  one in five SWE-bench Verified patches that the original tests passed.

## Check that the tests can fail

A black-box suite with thin assertions passes broken code. Mutation testing
changes the code on purpose, for example by flipping a condition or dropping
a line, and reports each change that no test caught. Run it on the code a
change touches when the suite's strength is in doubt, and add the missing
assertions at the boundary.

## Properties, metamorphic relations, and differential checks

Example cases cover the inputs someone thought of. Three kinds of check reach
further, and all stay black-box:

- A property test generates many inputs and checks a rule that must hold for
  all of them: a round trip returns the input, sorting keeps every element,
  applying an operation twice changes nothing more. Use one when the spec
  states a rule rather than a list of examples.
- A metamorphic test checks how the outputs of related inputs relate, when
  no source gives the exact output: adding a filter never returns more rows,
  and shuffling a list of integers leaves its sum unchanged. Use one for
  search, ranking, and numeric code.
- A differential test runs two implementations on the same inputs and
  compares outputs: old against new for a refactor or rewrite, or a simple
  reference against an optimized version.

## Golden files

When the output is too large to write inline, such as a report, a generated
file, or a full API response, store the expected output in a file next to the
test and compare against it.

- Commit the golden file and review its diff like code. A person can check an
  input and expected-output pair faster than an agent-written assertion.
- Keep one golden file per scenario, small enough to read.
- Regenerate a golden file only for a behavior change the user approved, and
  review the diff before committing it.

A golden file checks what the program outputs for an input. `proof` Rule 7's
ban on asserting literal text covers config and docs, which you prove by
running whatever reads them.

## Regression guards for bugs

1. Reproduce the bug at the outermost boundary that shows it, with the input
   from the report.
2. Run the test and watch it fail for the reason the report describes.
3. Fix the code and watch the same test pass.
4. Keep the test as the guard against the bug coming back. Name it after the
   behavior, and link the issue when there is one.

Use an integration test when the bug needs a real dependency to appear. Use a
unit test only when neither can reproduce it, such as a race inside one data
structure.

## Integration tests

- Run the real dependency, such as a database in a container, instead of a
  mock of its client. Agents add mocks more often than people do, and a
  mocked client cannot show that a query or message works.
- Cover what only the real dependency can check: query results,
  constraints, transactions, serialization, and wire formats.
- Keep each test on the adapter. Black-box tests above the adapter cover the
  behavior that uses it.

## Explore with an agent, prove with a test

An agent that clicks through a running app finds problems worth checking,
but its verdict is exploration, not proof. In one benchmark, the best agent
found a third of the defects, and agents mistook slow rendering for failures.
Turn each finding worth keeping into a scripted test whose result needs no
agent to judge, with its inputs and expected outputs written down, and cite
that test as the evidence.

## Canon

Research on testing agent-written code:

- Konstantinou, Degiovanni, and Papadakis,
  [Can we find bugs using LLM-generated oracles?](https://arxiv.org/abs/2410.21136)
  (2024, revised 2026): in most cases, LLM-generated assertions encode what
  the code does now, which makes its bugs hard to catch.
- Zhao, Zhou, and Cohen,
  [Evaluating and Mitigating the Misguidance Effect of Buggy Code in LLM-Generated Unit Tests](https://arxiv.org/abs/2607.22883)
  (ISSTA 2026): buggy code in the prompt steers models toward tests that
  confirm the bug. Generating tests from a specification reduces this.
- Tufano et al. (Google),
  [Grounding AI Agents in Contracts](https://arxiv.org/abs/2608.17177)
  (2026): an agent that writes each function's contract before its tests
  caught 9.8 percentage points more Google production bugs than one that
  wrote tests from the code.
- Zhong, Raghunathan, and Carlini,
  [ImpossibleBench](https://arxiv.org/abs/2510.20270) (2025): when tests
  contradict the spec, frontier models often make them pass anyway by
  editing or deleting tests, overloading comparison operators, or
  special-casing the test inputs. Hiding the tests cut cheating to near zero
  but also lowered legitimate scores. Read-only tests stopped test edits but
  not special-casing or operator overloading. A stricter prompt cut GPT-5's
  cheating on one task set from 92% to 1%. An option to flag the conflict for
  a person cut GPT-5's rate from 54% to 9%, with much less effect on Claude
  Opus 4.1.
- Kong et al.,
  [WebTestBench](https://arxiv.org/abs/2603.25226) (2026): computer-use
  agents testing 100 AI-generated web apps all scored below 30% F1 at finding
  defects, and mistook rendering delays and asynchronous updates for
  failures.
- Alonso, Yovine, and Braberman,
  [TDAD: Test-Driven Agentic Development](https://arxiv.org/abs/2603.17973)
  (2026): telling an agent which existing tests cover its change cut
  regressions by 70%. TDD instructions alone raised them.
- Chen et al.,
  [Rethinking the Value of Agent-Generated Tests](https://arxiv.org/abs/2602.07900)
  (2026): prompting agents to write more or fewer tests did not change how
  many SWE-bench Verified tasks they solved.
- Hora and Robbes,
  [Are Coding Agents Generating Over-Mocked Tests?](https://arxiv.org/abs/2602.00409)
  (MSR 2026): 36% of agent commits that touch tests add mocks, against 26%
  for other committers.
- Mündler et al.,
  [SWT-Bench](https://arxiv.org/abs/2406.12952) (2024): tests that fail
  before a fix and pass after it doubled the precision of an agent's fixes.
- He et al.,
  [Effective LLM Code Refinement via Property-Oriented and Structurally Minimal Feedback](https://arxiv.org/abs/2506.18315)
  (2026): feedback from property checks beat refinement with generated
  example tests by up to 13.4% pass@1.
- Maaz, DeVoe, Hatfield-Dodds, and Carlini (Anthropic),
  [Agentic Property-Based Testing](https://arxiv.org/abs/2510.09907)
  (2025): property tests written by an agent found real bugs in popular
  Python packages, several since patched upstream.
- Wang, Pradel, and Liu,
  [Are "Solved Issues" in SWE-bench Really Solved Correctly?](https://arxiv.org/abs/2503.15223)
  (ICSE 2026): differential testing against the reference patch found that
  29.6% of test-passing patches do not match its behavior.
- Eniser et al.,
  [Towards Translating Real-World Code with LLMs](https://arxiv.org/abs/2405.11514)
  (2025): differential fuzzing checks that a translated program gives the
  same outputs as the original, with no existing tests.
- Whitfill, Wu, Becker, and Rush (METR),
  [Many SWE-bench-Passing PRs Would Not Be Merged into Main](https://metr.org/notes/2026-03-10-many-swe-bench-passing-prs-would-not-be-merged-into-main/)
  (2026): maintainers would reject about half of the patches that pass the
  hidden tests.
- Yu et al.,
  [SWE-ABS](https://arxiv.org/abs/2603.00520) (ICML 2026): strengthened
  tests reject 19.7% of patches that passed the original SWE-bench Verified
  tests.
- Foster et al. (Meta),
  [Mutation-Guided LLM-based Test Generation at Meta](https://arxiv.org/abs/2501.12862)
  (FSE 2025): engineers accepted 73% of generated unit tests when each test
  had to catch a seeded fault. Generated unit tests keep their value when
  each one must catch a specific fault.

Test design:

- NIST,
  [Automated Combinatorial Testing for Software](https://csrc.nist.gov/projects/automated-combinatorial-testing-for-software):
  across NIST's studies, most failures came from one or two interacting
  parameters, and all from six or fewer.
- Chen et al.,
  [Metamorphic Testing: A Review of Challenges and Opportunities](https://doi.org/10.1145/3143561)
  (ACM Computing Surveys, 2018): relations between the outputs of related
  inputs give a check when no exact expected output exists.

Practice:

- Playwright,
  [Test agents](https://playwright.dev/docs/test-agents) (1.56, 2025): a
  planner explores the app, a generator writes ordinary test files from the
  plan, and a healer patches failing tests and can mark one skipped when it
  judges the feature broken.
- Anthropic,
  [Claude Code best practices](https://code.claude.com/docs/en/best-practices):
  give the agent a check it can run, including a diff against a fixture, and
  have a fresh model check the result so the agent doing the work is not the
  one grading it.
- Justin Young (Anthropic),
  [Effective harnesses for long-running agents](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents)
  (2025): the agent passed unit tests and curl checks while features still
  failed end to end. Testing through the browser as a user would caught the
  failures, and the harness tells agents never to remove or edit tests.
- Nicholas Carlini (Anthropic),
  [Building a C compiler with a team of parallel Claudes](https://www.anthropic.com/engineering/building-c-compiler)
  (2026): agents worked against external compiler test suites, with GCC as
  the reference to compare output against. The verifier has to be close to
  perfect, or the agents solve the wrong problem.
- Simon Willison,
  [porting JustHTML with Codex CLI](https://simonwillison.net/2025/Dec/15/porting-justhtml/)
  (2025): an implementation-independent suite of over 9,000 cases let an
  agent port a whole parser with little steering. His
  [First run the tests](https://simonwillison.net/guides/agentic-engineering-patterns/first-run-the-tests/)
  (2026) has the agent run the existing suite before it changes anything.
- Naresh Jain,
  [Are Harnesses Worth the Cost?](https://martinfowler.com/articles/are-harnesses-worth-the-cost.html)
  (2026): an API-level harness of contract checks, HTTP response tests, and
  side-effect assertions took a low-cost model from 3 of 10 successful runs
  to 10 of 10. The sample is small.
- Ivett Ördög,
  [Approved Scenarios](https://lexler.github.io/augmented-coding-patterns/patterns/approved-scenarios/)
  (Augmented Coding Patterns): people review input and expected-output
  fixtures as diffs instead of reading agent-written assertions.
- Lada Kesseler,
  [Tessl podcast episode 120](https://tessl.io/podcast/120) (2026): she keeps
  the high-level behavioral tests where the agent cannot edit them and lets
  it work on everything below.
- Birgitta Böckeler,
  [Maintainability sensors for coding agents](https://martinfowler.com/articles/sensors-for-coding-agents.html)
  (2026): teams are moving toward end-to-end acceptance tests, which often
  assert too little. Mutation testing shows the gaps.
- Syntax episode 1049,
  [WTF is a Software Factory?](https://syntax.fm/show/1049/wtf-is-a-software-factory)
  (2026), with Adam Jacob: a black-box suite kept outside the agent's context
  is the first thing to build, because it makes refactoring safe.
  Integration tests stay useful, but an agent can edit them to prove its own
  change.

Where practitioners disagree: Kent Beck
([Augmented Coding](https://newsletter.kentbeck.com/p/augmented-coding-beyond-the-vibes),
2025) runs agents under strict TDD and treats a disabled or deleted test as
cheating. Simon Willison
([Red/green TDD](https://simonwillison.net/guides/agentic-engineering-patterns/red-green-tdd/),
2026) and the Thoughtworks
[retreat findings](https://www.thoughtworks.com/content/dam/thoughtworks/documents/report/tw_future%20_of_software_development_retreat_%20key_takeaways.pdf)
(2026) argue that tests written first help agents. Birgitta Böckeler's
[experiment](https://martinfowler.com/articles/exploring-gen-ai/tdd-in-the-agent-loop.html)
(2026) found TDD instructions gave no quality gain at three times the token
cost. Emily Bache
([2026](https://coding-is-like-cooking.info/2026/09/the-last-year-has-changed-everything-i-knew-about-tdd-after-20-years/))
argues that Böckeler's experiment used too thin a TDD prompt to settle the
question. Consult requires a failing test first only when the failure is
itself the evidence, as in `proof` Rule 6, and leaves the rest of the
workflow to the team. Both sides agree that tests the agent cannot weaken are
what matter.
