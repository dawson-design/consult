# Test-Theater Traps

Use this when a test looks related to a change but would not prove real
behavior. Each row's Exception says when the test is worth keeping.

| Trap | Do this instead | Exception |
|---|---|---|
| Unit test for chain functions that hold no business rule. | Keep black-box tests above and below the chain, with more input cases there when a stage has many branches. | The test guards a fixed bug in that stage that boundary assertions cannot reproduce. |
| Error test only asserts that an error happens. | Assert the message, code, and structured fields the consumer observes at the outermost boundary. | The error path is purely internal and no consumer observes it. |
| Test needs many mocks and deep setup. | Simplify the boundary: extract pure transforms and push effects to the edge before adding more mocks. | The test crosses a true system boundary such as clock, network, process, filesystem, or expensive infrastructure. |
| Parameterized across every imagined input. | Cover behaviors named by the requirement and real boundary cases: security, data loss, parsing edges that exist in production data. | The function is a parser, validator, or security gate where input-space coverage is the contract. |
| Test asserts literal text in a data or wiring file. | Exercise the consumer instead: run, load, parse, or inspect the file and assert or report the result. If no consumer is involved, delete the test. | The literal string is a public contract, or generated code owns the file and the test enters through the generator. |
| Test asserts framework or language behavior. | Test your code's use of the framework at the boundary where you bind to it. | A specific framework bug or version pin is what the test proves, with a comment naming the bug. |
| Test asserts a removed file or directory stays absent. | Use targeted search, lint, or a pre-commit hook for repo-structure guards. | A migration-era guard is explicitly time-boxed in a comment with a removal date. |
| Test asserts a hardcoded constant or trivial passthrough. | Delete it when there is no behavior. | The constant is part of a public protocol, error code, schema field, or other consumer contract. |
| Test asserts only that a mock was called. | Assert the resulting external state: response, outbox row, captured log, metric, event, or persisted record. | The call itself is the contract, such as an outbox writer where row creation is the behavior. |
