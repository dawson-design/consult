# Build Stages

Use this when a change spans more than one `workflow` Rule 10 stage,
behavior slices, a removal or rename, or a phased schema rollout.

## Scope

- Stages order the build of one change. They are not folders, modules, or
  code layers; `architecture` owns code structure.
- When the plan splits the work into behavior slices, each slice runs its own
  stages and gates.
- A removal takes out each consumer before the thing it consumes. A rename
  adds the new name, moves readers to it, then removes the old name, as
  `refactoring` and `database` phase it.

## Proof at each stage

| Stage | Proof before the next stage | Avoid |
|---|---|---|
| Data | Migrations run forward, and back where reversible. Integration tests against the real database show that each constraint the schema enforces rejects bad rows. Domain types pass the type checker where the language has one. Mark any invariant that neither enforces as unproven at the gate; the contracts stage's boundary tests prove it. | Unit tests of model or parser internals. |
| Contracts | The contract source validates. Black-box tests written from it fail first, then pass, for each response the shell produces without transformation logic, such as input rejection, auth failures, not-found, and plain reads and writes. | Tests that pass against a stub. A new endpoint whose valid response needs transformation logic gets its valid path and its tests in the transformations stage; until then that path returns an explicit not-implemented error that no test asserts. An existing endpoint keeps its current valid response until the transformations stage changes it. |
| Transformations | Black-box tests through the contract, with expected outputs from the spec, for each endpoint whose valid response the logic computes. Earlier stages' tests stay green unchanged. | Editing an earlier stage's test to fit the logic. |

## Handoffs

- `proof`: the checks each stage owes.
- `contract-first` and `domain-modeling`: the shapes each gate approves.
- `database`: phased rollout and migration safety.
