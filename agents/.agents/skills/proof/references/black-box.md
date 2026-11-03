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
pass. The Canon section lists the studies behind both.

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

## Canon

Research on testing agent-written code:

- Konstantinou, Degiovanni, and Papadakis,
  [Can we find bugs using LLM-generated oracles?](https://arxiv.org/abs/2410.21136)
  (2024, revised 2026): LLM-generated assertions mostly encode what the code
  does now, bugs included.
- Zhao, Zhou, and Cohen,
  [Evaluating and Mitigating the Misguidance Effect of Buggy Code in LLM-Generated Unit Tests](https://arxiv.org/abs/2607.22883)
  (ISSTA 2026): buggy code in the prompt steers tests toward confirming the
  bug; tests from a specification resist it.
- Tufano et al. (Google),
  [Grounding AI Agents in Contracts](https://arxiv.org/abs/2608.17177)
  (2026): writing each function's contract before its tests caught 9.8
  percentage points more production bugs.
- Zhong, Raghunathan, and Carlini,
  [ImpossibleBench](https://arxiv.org/abs/2510.20270) (2025): when tests
  contradict the spec, frontier models edit tests, overload comparisons, or
  special-case inputs. A prompt to stop and flag the conflict cut GPT-5's
  cheating on one task set from 92% to 1%.
- Kong et al.,
  [WebTestBench](https://arxiv.org/abs/2603.25226) (2026): computer-use
  agents found under 30% of defects in AI-generated web apps and mistook
  rendering delays for failures.
- Alonso, Yovine, and Braberman,
  [TDAD: Test-Driven Agentic Development](https://arxiv.org/abs/2603.17973)
  (2026): telling an agent which existing tests cover its change cut
  regressions by 70%.
- Chen et al.,
  [Rethinking the Value of Agent-Generated Tests](https://arxiv.org/abs/2602.07900)
  (2026): asking agents for more or fewer tests did not change solve rates.
- Hora and Robbes,
  [Are Coding Agents Generating Over-Mocked Tests?](https://arxiv.org/abs/2602.00409)
  (MSR 2026): 36% of agent commits that touch tests add mocks, against 26%
  for other committers.
- Mündler et al.,
  [SWT-Bench](https://arxiv.org/abs/2406.12952) (2024): fail-before,
  pass-after tests doubled the precision of agent fixes.
- He et al.,
  [Effective LLM Code Refinement via Property-Oriented and Structurally Minimal Feedback](https://arxiv.org/abs/2506.18315)
  (2026): property-check feedback beat generated example tests by up to
  13.4% pass@1.
- Maaz, DeVoe, Hatfield-Dodds, and Carlini (Anthropic),
  [Agentic Property-Based Testing](https://arxiv.org/abs/2510.09907)
  (2025): agent-written property tests found real bugs in popular Python
  packages.
- Wang, Pradel, and Liu,
  [Are "Solved Issues" in SWE-bench Really Solved Correctly?](https://arxiv.org/abs/2503.15223)
  (ICSE 2026): differential testing showed 29.6% of test-passing patches
  differ from the reference behavior.
- Eniser et al.,
  [Towards Translating Real-World Code with LLMs](https://arxiv.org/abs/2405.11514)
  (2025): differential fuzzing checks a translation against the original.
- Whitfill, Wu, Becker, and Rush (METR),
  [Many SWE-bench-Passing PRs Would Not Be Merged into Main](https://metr.org/notes/2026-03-10-many-swe-bench-passing-prs-would-not-be-merged-into-main/)
  (2026): maintainers would reject about half of hidden-test-passing
  patches.
- Yu et al.,
  [SWE-ABS](https://arxiv.org/abs/2603.00520) (ICML 2026): strengthened
  tests reject 19.7% of patches the original SWE-bench Verified tests
  passed.
- Foster et al. (Meta),
  [Mutation-Guided LLM-based Test Generation at Meta](https://arxiv.org/abs/2501.12862)
  (FSE 2025): engineers accepted 73% of generated tests when each had to
  catch a seeded fault.

Test design:

- NIST,
  [Automated Combinatorial Testing for Software](https://csrc.nist.gov/projects/automated-combinatorial-testing-for-software):
  most failures involve one or two interacting parameters.
- Chen et al.,
  [Metamorphic Testing: A Review of Challenges and Opportunities](https://doi.org/10.1145/3143561)
  (ACM Computing Surveys, 2018).

Practice:

- Playwright, [Test agents](https://playwright.dev/docs/test-agents) (1.56,
  2025): its healer patches failing tests and can mark one skipped.
- Anthropic,
  [Claude Code best practices](https://code.claude.com/docs/en/best-practices):
  give the agent a runnable check, and have a fresh model grade the result.
- Justin Young (Anthropic),
  [Effective harnesses for long-running agents](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents)
  (2025): unit tests passed while features failed end to end.
- Nicholas Carlini (Anthropic),
  [Building a C compiler with a team of parallel Claudes](https://www.anthropic.com/engineering/building-c-compiler)
  (2026): GCC as the reference oracle; the verifier must be near perfect.
- Simon Willison,
  [porting JustHTML with Codex CLI](https://simonwillison.net/2025/Dec/15/porting-justhtml/)
  (2025) and
  [First run the tests](https://simonwillison.net/guides/agentic-engineering-patterns/first-run-the-tests/)
  (2026).
- Naresh Jain,
  [Are Harnesses Worth the Cost?](https://martinfowler.com/articles/are-harnesses-worth-the-cost.html)
  (2026): an API-level harness took a low-cost model from 3 to 10 of 10
  runs, on a small sample.
- Ivett Ördög,
  [Approved Scenarios](https://lexler.github.io/augmented-coding-patterns/patterns/approved-scenarios/):
  people review input and expected-output fixtures as diffs.
- Lada Kesseler, [Tessl podcast episode 120](https://tessl.io/podcast/120)
  (2026): high-level behavioral tests kept out of the agent's reach.
- Birgitta Böckeler,
  [Maintainability sensors for coding agents](https://martinfowler.com/articles/sensors-for-coding-agents.html)
  (2026): end-to-end acceptance tests often assert too little.
- Syntax episode 1049,
  [WTF is a Software Factory?](https://syntax.fm/show/1049/wtf-is-a-software-factory)
  (2026), with Adam Jacob: a black-box suite outside the agent's context
  makes refactoring safe.

Where practitioners disagree on TDD: Kent Beck
([Augmented Coding](https://newsletter.kentbeck.com/p/augmented-coding-beyond-the-vibes),
2025), Simon Willison
([Red/green TDD](https://simonwillison.net/guides/agentic-engineering-patterns/red-green-tdd/),
2026), and the Thoughtworks
[retreat findings](https://www.thoughtworks.com/content/dam/thoughtworks/documents/report/tw_future%20_of_software_development_retreat_%20key_takeaways.pdf)
(2026) favor tests first. Birgitta Böckeler's
[experiment](https://martinfowler.com/articles/exploring-gen-ai/tdd-in-the-agent-loop.html)
(2026) found no gain at three times the cost, and Emily Bache
([2026](https://coding-is-like-cooking.info/2026/09/the-last-year-has-changed-everything-i-knew-about-tdd-after-20-years/))
argues its prompt was too thin to settle it. Consult requires a failing test
first only when the failure is the evidence (`proof` Rule 6). Both sides
agree that tests the agent cannot weaken are what matter.
