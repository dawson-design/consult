# Tests That Prove Behavior

Use this when a test looks related to a change but may not prove real
behavior. Each rule ends with the case where a narrower test is worth
keeping.

- **Chains** (pipeline, parser, validator, middleware): test black-box above
  and below the chain, with one case for each way the data changes shape at
  each seam. Unit-test a stage only when it holds pure domain logic, is a
  public API, or guards a fixed bug that boundary tests cannot reproduce.
- **Errors:** assert the message, code, and structured fields the consumer
  observes at the outermost boundary. An internal error path that no
  consumer observes needs only to be raised.
- **Setup:** when a test needs many mocks, simplify the boundary first:
  extract pure transforms and push effects to the edge. Give protocol code a
  pure bytes-in, bytes-out API and test that. Mock only a true system
  boundary such as the clock, network, process, filesystem, or expensive
  infrastructure.
- **Pipelines:** assert that destination counts reconcile with source counts
  plus rejects, and that a failed load leaves no partial write. An
  idempotent load whose rerun repairs a partial write needs only the count
  check.
- **Inputs:** cover the behaviors the requirement names and real boundary
  cases: security, data loss, and parsing edges that exist in production
  data. Cover the input space broadly only for a parser, validator, or
  security gate, where that coverage is the contract.
- **Removals:** delete or update the tests, docs, and examples that named the
  removed file, route, or option; test the behavior that remains; and confirm
  stale references are gone with a targeted search. Test the absence itself
  only when rejection is the surviving public behavior: a security denylist,
  an authorization block (`403`), an explicit API rejection (`404`, `410`), a
  compatibility error, or a migration guard with an owner and removal date.
- **Constants and passthroughs:** delete a test that asserts no behavior.
  Keep it when the constant is part of a public protocol, error code, schema
  field, or other consumer contract.
- **Calls:** assert the resulting external state: response, outbox row,
  captured log, metric, event, or persisted record. Assert the call itself
  only when it is the contract, such as an outbox writer where creating the
  row is the behavior.
