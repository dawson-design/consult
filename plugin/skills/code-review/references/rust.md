# Rust review reference

Use when reviewing Rust code in the diff. Apply this alongside the main
`code-review` skill workflow.

## Tooling that should be passing

- `cargo fmt --all -- --check`: formatting is non-negotiable.
- `cargo clippy --all-targets --all-features -- -D warnings`: clippy
  warnings are errors. Diffs that downgrade or `#[allow(...)]` lints
  need a justification.
- `cargo test --all`: for libraries, run with `--no-default-features`
  too if features are non-trivial.
- `cargo deny check` (if configured): flags advisories, license
  changes, and disallowed sources.
- `Cargo.lock` is committed by default for applications and
  libraries (Cargo's guidance since 2023). A library that commits it
  still needs CI against latest dependencies, because consumers
  ignore its lockfile.

## High-signal review checks

- Error handling: prefer `?` propagation with `Result` and concrete
  error enums (`thiserror` for libraries, `anyhow` only for app
  boundaries). Reject `.unwrap()` / `.expect()` in non-test code unless
  the invariant is provably enforced and commented.
- Panics: indexing (`v[i]`), `unwrap`, `expect`, `unreachable!`,
  `todo!`, integer division, slice ranges. Each one needs a why.
- Async: blocking work inside `async fn` (file I/O, CPU-heavy
  loops) starves the runtime. Look for `std::thread::sleep`, blocking
  DB drivers, or a `std::sync::Mutex` guard held across `.await`.
  A `std::sync::Mutex` locked briefly and released before `.await` is
  fine and is Tokio's recommended default.
- `Send + Sync`: spawned futures and shared state must satisfy the
  bounds. `Rc`, `RefCell`, raw pointers in spawned tasks are red flags.
- Lifetimes vs clones: a sudden `.clone()` on a hot path is worth
  questioning, but so is a lifetime gymnastics that obscures intent.
  Pick the simpler shape unless benchmarks justify otherwise.
- `Drop` order and resource leaks: scope guards, file handles,
  network connections. `mem::forget`, `ManuallyDrop`, `Box::leak` need
  explicit justification.
- Unsafe: every `unsafe` block needs a comment naming the
  invariants the caller must uphold. New unsafe code without a safety
  comment is a blocker.
- Public API: breaking changes to `pub` items in libraries trigger
  a semver bump. Adding `#[non_exhaustive]` to enums/structs is a
  common forward-compatibility move worth checking.
- Allocations on hot paths: `Vec::new` in a loop, `format!` for
  logging behind a level check, `String` cloning where `&str` would
  do. Match against the project's perf gates.

## Anti-patterns / red flags

- `unwrap()` or `expect()` outside tests with no explanatory comment.
- `Mutex` or `RwLock` held across `.await`.
- `tokio::spawn` without joining or storing the handle.
- New `unsafe` block with no `// SAFETY:` comment.
- `#[allow(clippy::*)]` added without a one-line reason.
- `Box<dyn Error>` in library public API (use a typed error).
- Re-exporting `anyhow::Error` from a library boundary.
- `panic!` as control flow.

## Sources

- The Rust API Guidelines: <https://rust-lang.github.io/api-guidelines/>
- Clippy lint index: <https://rust-lang.github.io/rust-clippy/>
- Tokio: Common pitfalls in async code:
  <https://tokio.rs/tokio/topics/bridging>
- Rustonomicon (unsafe invariants): <https://doc.rust-lang.org/nomicon/>
- thiserror / anyhow guidance:
  <https://docs.rs/thiserror/> · <https://docs.rs/anyhow/>
