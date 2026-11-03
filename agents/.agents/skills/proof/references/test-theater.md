# Test-Theater Traps

Use this when a test looks related to a change but would not prove real
behavior. Each row's Exception says when the test is worth keeping.

| Trap | Do this instead | Exception |
|---|---|---|
| Unit test for each function in a chain (pipeline, parser, validator, middleware) that holds no business rule. | Keep black-box tests above and below the chain, with one case for each way the data changes shape at each seam. | The stage holds pure domain logic, is a public API, or guards a fixed bug that boundary tests cannot reproduce. |
| Error test only asserts that an error happens. | Assert the message, code, and structured fields the consumer observes at the outermost boundary. | The error path is purely internal and no consumer observes it. |
| Test needs many mocks and deep setup. | Simplify the boundary: extract pure transforms and push effects to the edge before adding more mocks. Give protocol code a pure bytes-in, bytes-out API and test that, not a mocked socket. | The test crosses a true system boundary such as clock, network, process, filesystem, or expensive infrastructure. |
| Pipeline test only checks that the run finished. | Assert that destination counts reconcile with source counts plus rejects, and that a failed load leaves no partial write. | The load is idempotent and a rerun repairs a partial write. |
| Parameterized across every imagined input. | Cover behaviors named by the requirement and real boundary cases: security, data loss, parsing edges that exist in production data. | The function is a parser, validator, or security gate where input-space coverage is the contract. |
| Test asserts a removed file, route, or option stays absent. | Delete or update the tests, docs, and examples that named it, test the behavior that remains, and confirm stale references are gone with a targeted search. | Rejection is the surviving public behavior: a security denylist, an authorization block (`403`), an explicit API rejection (`404`, `410`), a compatibility error, or a migration guard with an owner and removal date. |
| Test asserts a hardcoded constant or trivial passthrough. | Delete it when there is no behavior. | The constant is part of a public protocol, error code, schema field, or other consumer contract. |
| Test asserts only that a mock was called. | Assert the resulting external state: response, outbox row, captured log, metric, event, or persisted record. | The call itself is the contract, such as an outbox writer where row creation is the behavior. |
