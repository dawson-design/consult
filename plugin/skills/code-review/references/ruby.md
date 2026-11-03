# Ruby review reference

Use when reviewing Ruby or Rails code in the diff. Targets Ruby 3.x on Rails
7.x and 8.x. Check version-specific claims with `official-source-check`.

## Domain-modeling bias

Route deeper modeling questions to `domain-modeling`.

- Prefer `Data.define` (Ruby 3.2+) for value objects over `Struct` or
  `OpenStruct`.
- Prefer module functions over stateful `Manager`, `Helper`, or `Service`
  classes that have no real invariants.
- `freeze` shared structures instead of copying them defensively.
- Keep Active Record at the edge. Domain logic takes and returns value
  objects, not AR records.
- `def initialize(*args, **kwargs)` that swallows arbitrary input is a
  finding.
- `raise "message"` for an expected domain outcome is a finding: use a named
  exception or a result variant. A `rescue => e` with no logging and no
  re-raise is a finding.
- `Time.now` in domain logic is a finding: use `Time.current` or an injected
  clock.
- Monetary math without `BigDecimal` or integer cents, or mixing currencies,
  is a finding. See `domain-modeling` Rule 8.

## Tooling

- New `rubocop:disable` comments and `brakeman.ignore` entries need a
  reason.

## Pattern matching and syntax traps

- `case/in` without `else` raises `NoMatchingPatternError`. User-facing
  logic needs an `else`.
- Hash patterns match partially. Use `**nil` for a closed match.
- Matching against an existing variable needs the pin operator `^`. A bare
  name always rebinds, so the pattern matches anything.
- `def invoke = puts "x" if @active` parses as a conditional method
  definition, so the method is silently never defined. Endless methods take
  no trailing modifier.

## Rails

- `params.expect` needs double brackets for arrays of hashes:
  `params.expect(post: [:title, comments: [[:body]]])`.
- `rate_limit` stores counters in `Rails.cache`. In multi-process production
  that must be a shared cache store, or each worker counts alone.
- With Packwerk, dependency enforcement pays off. Privacy enforcement often
  hurts readability. Default to a monolith, and extract a service only when
  scaling, security domain, or team ownership truly diverges.

## Active Record

- `load_async` needs a pool of at least `thread_count +
  global_executor_concurrency + 1` in `database.yml`, or Puma threads
  starve.
- Adding `normalizes` to an existing column needs a backfill. It does not
  rewrite stored rows.
- `encrypts` is non-deterministic by default. `deterministic: true` on a
  column nobody queries is over-permissive. Changing the scheme without
  `previous:` orphans existing rows.
- `upsert_all(unique_by:)` and `find_or_create_by` need a database unique
  index, or concurrent writers race.
- `strict_loading` should raise in dev and test, and log in production until
  clean. `:n_plus_one_only` mode allows single-record lazy loads.
- No HTTP calls inside `transaction do`: the row lock is held for the whole
  call. Enqueue jobs after commit.
- Dangerous migrations go to the `database` skill. A Rails repo should run
  `strong_migrations`.

## Security

- Background jobs re-check authorization. A job that loads
  `Document.find(id)` is unscoped even when the controller was scoped.
- Never permit `:type` from a form: it lets the client pick the STI class.
- Redirects use `url_from(params[:return_to]) || root_path` with
  `raise_on_open_redirects = true`. A hand-rolled "starts with `/`" check
  lets `//evil.com` through.
- `JWT.decode` always passes `algorithm:`.
- Regexes that validate input anchor with `\A` and `\z`, not `^` and `$`.
  This includes CORS origin regexes. Never combine `origins '*'` with
  `credentials: true`.
- Set `Regexp.timeout` (Ruby 3.2+) globally against ReDoS.
- ActiveStorage `variant(...)` takes only allow-listed transformations, never
  params. Force `disposition: "attachment"` for non-images, and serve user
  uploads from a separate origin.
- `YAML.unsafe_load`, `Marshal.load`, and
  `JSON.parse(input, create_additions: true)` on untrusted data are
  findings.
- Production must populate `config.hosts`, or password-reset links can
  point at an attacker's host.
- A `master.key` in git history means rotating every credential.

## Hotwire

- Reach for the simplest layer that works: HTML and CSS, Turbo Drive, Turbo
  Frames, Turbo Streams, Stimulus, then custom JS.
- Turbo morphing keys on stable `id` attributes, so random container ids
  break it. It only fires when the start and end URLs are the same.
- A raw `fetch` from Stimulus loses the CSRF token. Use `Request.js` or
  `data-turbo-method`.

## Testing

- `before(:all)` with DB writes leaks records, because transactional
  fixtures wrap each example, not the group. Use `let_it_be`.
- `sleep` in system specs is a finding. Use Capybara's waiting matchers.

## Type checking

- Treat each `T.untyped`, `untyped`, `T.must`, or `T.cast` as a TODO finding.
