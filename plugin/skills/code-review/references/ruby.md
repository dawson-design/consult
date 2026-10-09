# Ruby review reference

Use when reviewing Ruby (or Rails) code in the diff. Apply this
alongside the main `code-review` skill workflow. Targets Ruby 3.x on
Rails 7.x / 8.x.

## Domain-modeling bias (apply first)

Ruby's culture leans heavily on objects with state. The
`domain-modeling` skill's doctrine still applies:

- Prefer `Data.define` (Ruby 3.2+) for value objects: frozen,
  structural equality, `with(x: 1)` copy-update, pattern-match
  support. `Struct.new(..., keyword_init: true)` for read-only data
  is needs-modernisation; `OpenStruct` is being deprecated: flag it.
- Pure module functions over instance state. Classes that exist only
  to hold mutable scratchpads (`Manager`, `Helper`, `Service` with
  three methods and no real invariants) are smells.
- `freeze` shared structures; immutable-by-default beats defensive
  copying.
- Isolate Active Record at the edge: domain logic accepts and returns
  value objects, not AR records, so it stays testable.
- Parse untrusted input into typed values once (`params.expect`,
  `dry-validation`, custom value objects) and let downstream code
  trust them.

## Tooling that should be passing

- `bin/rubocop`: house style. Rails 7.2+ defaults to
  `rubocop-rails-omakase`; Standard Ruby is the polyglot-org pick.
  Mixing both is a flag. New `rubocop:disable` comments need a reason.
- `bin/rspec` (or `bin/rails test` for Minitest): narrow first; CI
  runs the full suite. Don't mix runners in one project.
- `bin/brakeman --quiet --no-pager --exit-on-warn --exit-on-error`:
  without `--exit-on-warn`, builds silently pass on new warnings.
  New `brakeman.ignore` entries need a `note:` justification.
- `bin/bundler-audit check --update`, plus `bin/importmap audit`
  (Rails 8): daily cron in CI. Rack CVEs need the same upgrade
  urgency as Rails.
- `erb_lint` for ERB-heavy apps; strict-locals on partials
  (`<%# locals: (name:, admin: false) %>`) is high-value.
- `Gemfile.lock` is multiplatform: `bundle lock --add-platform
  x86_64-linux aarch64-linux ruby`. Single-platform locks (Apple
  Silicon dev only) cause `Could not find nokogiri-X-x86_64-linux`
  in CI/Docker.
- For Sorbet/Steep projects: `srb tc` / `steep check` clean.

## Modern Ruby 3.x idioms

- `{x:, y:}` hash shorthand (3.1+) is the dominant idiom now.
  `{name: name, email: email}` is needs-modernisation.
- `case/in` is exhaustive (raises `NoMatchingPatternError`
  without `else`); add `else` in user-facing logic. Hash patterns are
  partial: use `**nil` for closed matches. The pin operator `^` is
  mandatory when matching against an existing variable; bare names
  always rebind (the most common reviewer-caught bug).
- Endless methods (`def name = @name`) only single-line, no
  `rescue`/`ensure`. Watch the trailing-modifier bug:
  `def invoke = puts "x" if @active` parses as `(def invoke = puts
  "x") if @active` and silently never defines the method.
- Anonymous forwarding `(...)` (3.1) and `(*, **, &)` (3.2) for
  trampolines; anonymous `&` is zero-allocation. Don't use `(...)`
  if the body inspects args.
- `it` block parameter (3.4) for one-line single-arg blocks. `_1`
  for multi-numbered; mixing `_1` with named block params is a
  `SyntaxError`.
- `# frozen_string_literal: true` on every file; CI runs with
  `RUBYOPT="-W:deprecated"` to surface 3.4 chilled-string mutations.
- `ruby2_keywords` is a transitional crutch: any new usage is a
  code smell.
- Refinements: niche. Acceptable for narrow uses; flag refinements
  applied across many files or overriding `+`/`==`/`<=>`.

## Performance and Object Shapes

- Lazy `||=` ivar memoisation creates many shapes per class,
  because ivars set in varying order each make a new shape. Classes
  that exceed the variation limit fall back to a hash
  (`SHAPE_TOO_COMPLEX`). Eagerly init ivars in `initialize`.
- `@result ||= compute` caches `false`/`nil` incorrectly. Use
  `defined?(@result) ? @result : (@result = compute)` when those are
  valid memoised values.
- YJIT in production for any Ruby ≥ 3.3. For fork-heavy servers
  (Unicorn / Pitchfork) enable YJIT *after* fork via
  `RubyVM::YJIT.enable` for better copy-on-write.
- Memory tuning: `MALLOC_ARENA_MAX=2` on glibc gives 25–40% RSS
  drop, or jemalloc ≥ 5.3 for fork-safety with Pitchfork.
- Threads vs Ractors vs Fibers: threaded Puma/Pitchfork for
  I/O-bound; Falcon + `async` for streaming/WebSockets (AR isn't
  async-aware; Sequel is); forked processes for CPU-bound. **Ractors
  remain experimental** and don't work with Rails or most native
  gems: flag any production Ractor code touching Rails internals.
- Rewrite reflexes:
  - `result += i.to_s` in a loop → `map(&:to_s).join` or
    `String.new(capacity: N) << i.to_s`.
  - `.select.map.compact` → `filter_map`.
  - `.where(...).each` → `find_each` / `in_batches`.
  - `.where(...).map(&:email)` → `.pluck(:email)`.
  - `.update` per-row in a loop → `update_all` (with explicit
    comment about skipped callbacks/timestamps).
  - `Rails.cache.fetch(key) { ... }` without `expires_in:`.

## Rails 8 stack

- `params.expect` over `params.require(...).permit(...)` in new
  controllers. The bug it fixes: `?user=hello` returns a String for
  which `permit` raises `NoMethodError` → uncaught 500.
  `params.expect` enforces structure and yields a clean 400. Common
  gotcha: arrays of hashes need double brackets:
  `params.expect(post: [:title, comments: [[:body]]])`.
- Solid Queue is the Rails 8 default ActiveJob backend.
  DB-backed via `FOR UPDATE SKIP LOCKED`. Sweet spot under ~2k
  jobs/min; above that, Sidekiq still wins. For non-trivial
  workloads configure a `queue` database via Rails multi-DB.
- Solid Cache is for fragment / HTTP caches: disk-backed,
  large-capacity, FIFO. Don't use it as a Redis substitute for
  rate-limit counters, leaderboards, distributed locks, or pub/sub.
- Solid Cable is DB-backed pub-sub with ~0.1s polling. For
  high-fanout chat / realtime, Postgres `LISTEN/NOTIFY` (`async`
  adapter) or Redis is still lower latency.
- Built-in `rate_limit to: 10, within: 3.minutes` is backed by
  `Rails.cache`: must use a distributed cache in multi-process
  production or each worker has its own counter. Pair with
  rack-attack for IP allow/blocklists.
- Native auth generator (`bin/rails generate authentication`)
  ships `User` + `Session` + `Current` + `Authentication` concern
  with `has_secure_password` and DB-tracked sessions. It does not
  ship signup, OmniAuth, MFA, account locking, or password
  complexity: for those, Devise (batteries-included) or Rodauth
  (security-sensitive: TOTP/passkeys/WebAuthn).
- Rails 8.1: ActiveJob Continuations (resumable multi-step jobs;
  each `step` must remain idempotent), structured event reporting,
  `format.md`, `has_many :posts, deprecated: true`, Kamal secrets
  via credentials. `config/ci.rb` is the new convention for a
  unified local + CI pipeline.

## ActiveRecord modern patterns

- `load_async` helps when ≥2 independent slow queries run for
  the same request. Pool size **≥ `thread_count +
  global_executor_concurrency + 1`** in `database.yml`, or Puma
  threads starve. Don't `load_async` inside a transaction held by
  the calling thread: connection-pinning can deadlock.
- `normalizes` (7.1) applies on assignment, persistence, *and*
  query. Migrating an existing column requires a backfill:
  `normalizes` doesn't retroactively rewrite stored data.
- `encrypts`: default non-deterministic (random IV, not
  queryable, highest security). `deterministic: true` is queryable
  but allows ciphertext correlation: flag on a non-queried column
  (over-permissive). Scheme switches without `previous:` orphan
  existing rows.
- `includes` / `preload` / `eager_load` / `joins`:

  | Method | Behavior | When |
  |---|---|---|
  | `joins(:posts)` | INNER JOIN; doesn't load posts | Filtering only; `.distinct` if duplicates |
  | `preload(:posts)` | 2 separate queries; can't `where` on posts | Default eager-load |
  | `eager_load(:posts)` | Single LEFT OUTER JOIN | Filter or order by association *and* load it |
  | `includes(:posts)` | Heuristic: `preload` unless detection flips it | Convenient but less explicit |

  Flag `Post.includes(:comments).where("comments.flagged")`: works
  only because Rails detects the string and switches to
  `eager_load`. Use the hash form
  `where(comments: { flagged: true })` or
  `eager_load(:comments)` explicitly.
- Strict loading in `:n_plus_one_only` mode: allows lazy load on
  single records, raises on collection iteration N+1. `:raise` in
  dev/test, `:log` in production until clean.
- Prosopite over Bullet for N+1 detection: SQL-fingerprint
  pattern matching catches cases Bullet misses. Have Prosopite
  raise in test.
- `insert_all` / `upsert_all` are 10–100× faster but bypass
  validations, callbacks, and timestamps. Flag missing DB unique
  index when relying on `unique_by:`. `returning:` is Postgres-only.
- Deferring enqueue until commit prevents the "background job runs
  against rolled-back row" bug. Rails 8.0 and 8.1: set
  `self.enqueue_after_transaction_commit = true` per job (default
  `false`; 8.0 deprecates the global config and 8.1 removes it).
  Check the release notes for later versions. Rails 7.2: `:always`,
  or the 7.2 default `:default`, which lets the queue adapter
  decide. Don't make HTTP calls inside `transaction do`: the
  row lock is held for the call duration.
- `strong_migrations` in the Gemfile catches dangerous
  migrations (adding `NOT NULL` without default; `change_column`
  rewriting the table; `add_index` on a large table without
  `algorithm: :concurrently`). Defer to the `database` skill for
  production data risk.
- Composite primary keys (7.1): insert-heavy workloads can
  become *slower* due to a larger PK index: measure. `belongs_to`
  from a CPK model needs `query_constraints: [...]`.

## Security review checklist

- SQL injection: ActiveRecord does not parameterise the
  string forms of `where`, `find_by_sql`, `select`, `from`,
  `joins`, `group`, `having`, `order`, `reorder`, `pluck`, `lock`,
  `update_all`, `delete_all`, or the calculate family
  (`sum`/`average`/`maximum`/`minimum`). Flag any string
  interpolation in those positions. `Arel.sql(user_input)` is an
  escape hatch: input must come from an explicit allow-list.
  `params[:sort]` flowing directly into `order` is the classic bug.
- IDOR is the most common Rails security bug in production.
  `Document.find(params[:id])` instead of
  `current_user.documents.find(params[:id])` is Critical. Use
  `after_action :verify_authorized` and `:verify_policy_scoped`.
  Re-check authorisation in background jobs:
  `DocumentExportJob.perform_later(doc.id, current_user.id)` with
  a job that loads via `Document.find(doc_id)` is unscoped.
- Mass assignment: never `permit!`. Never permit `:role`,
  `:admin`, `:owner_id`, `:account_id`, `:user_id`, `:type` (STI),
  `:approved`, or `:status` from form-driven controllers.
- XSS bypass list: `.html_safe` on a user-controlled string
  (the most common Rails XSS vector); `raw`; `<%==`; `sanitize`
  without explicit `tags:` and `attributes:`; translation keys
  ending `_html` with default values from params; `to_json` in JS
  contexts without escape. Verify `rails-html-sanitizer ≥ 1.6.1`.
- Open redirect: `redirect_to params[:next]` is the classic.
  Set `config.action_controller.raise_on_open_redirects = true`.
  Use `url_from(params[:return_to]) || root_path` and
  `redirect_back_or_to`. Hand-rolled "starts with `/`" checks are
  bypassed by `//evil.com` (protocol-relative URL).
- ActiveStorage: prefer libvips via `image_processing` with
  `ImageProcessing::Vips` and `variant_processor = :vips` (faster,
  sandboxed, no shell-out). Never pass params to `variant(...)`:
  allow-list transformations. Force `disposition: "attachment"` for
  non-images. Serve user uploads from a different origin so
  same-origin XSS can't reach the main app. Set `expires_in:` on
  signed_ids for sensitive content.
- Deserialisation: flag `YAML.unsafe_load`, `Marshal.load`, and
  `JSON.parse(input, create_additions: true)` on untrusted data.
  Verify `config.action_dispatch.cookies_serializer = :json`.
- JWT: always pass `algorithm:` to `JWT.decode` (older
  `ruby-jwt` accepted `alg: none`); don't accept both RS256 and
  HS256 on the same endpoint (algorithm-confusion attack uses the
  public key as the HMAC secret); short TTL + opaque refresh
  tokens; no PII in the JWT (it's base64, not encrypted).
- `config.hosts` empty in production by default: populate it,
  or you're vulnerable to host-header poisoning (password-reset
  emails pointing to attacker domain).
- CORS: anchor regex origins (`\Ahttps://example\.com\z`); never
  `origins '*'` with `credentials: true`.
- ReDoS: Ruby 3.2+ has built-in `Regexp.timeout = 1.0`: set it
  globally.
- Secrets: `master.key` in git history is full secret
  compromise: rotate immediately. Don't load dotenv in production.
  Centralise `credentials.dig(:foo) || ENV['FOO_BAR']` in a single
  config wrapper.

## Hotwire: Turbo and Stimulus

Decision rule, simplest to most powerful:

> HTML/CSS → Turbo Drive → Turbo Frames → Turbo Streams (refresh / morph) → Stimulus → custom JS

- Turbo 8 morphing (`turbo-refresh-method=morph`) keys on stable
  `id` attributes. Generated `dom_id(record)` is fine; randomised
  container IDs break it. Use `data-turbo-permanent` on elements
  that must survive (`<audio>`, embedded payment forms). Morphing
  only fires when start and end URLs are identical; doesn't help on
  `redirect_to other_path`.
- Stimulus smells: god controllers (20 targets, 15 actions);
  DOM queries by class instead of `data-*-target`; cross-controller
  comms via DOM lookup instead of custom events
  (`this.dispatch("opened")`) and Outlets (3.2+); `setTimeout` /
  `setInterval` not cleared in `disconnect()` (memory leaks under
  Turbo); direct `fetch` instead of `Request.js` /
  `data-turbo-method` (loses CSRF and content negotiation);
  controllers that mutate DOM the server also re-renders.

## Architecture

Decision matrix for where logic lives:

| Logic shape | Best fit |
|---|---|
| Persists single record + side effects | Model + concern + AR callback, OR a single PORO if the side effect is external |
| Multi-step transaction across aggregates | Service object with explicit `Result` (`Success`/`Failure` from dry-monads, or `Interactor`) |
| Complex query with reusable filters | Query object (PORO returning a relation) |
| Form with virtual attributes / multi-model save | `ActiveModel::Model` + `Attributes` + `Validations` |
| Validating external payload | dry-validation contract |
| Authorisation | Pundit (conservative) or action_policy (modern) |
| Value objects | `Data.define` (3.2+) |

- Don't nest transactions: use the `isolator` gem to detect
  non-atomic actions inside transactions.
- HTTP/jobs inside `transaction do` → `enqueue_after_transaction_commit`
  (Rails 7.2 default) or `after_commit_everywhere`.
- Concerns named by domain trait (`Trashable`, `Searchable`),
  not by mechanism (`Validations`, `Callbacks`, `Scopes`).
- Bag-of-params hashes; services without explicit return contracts;
  `Service.new(args).call` instead of `Service.call(args)`: flag.
- Modular monolith / Packwerk: dependency enforcement is the
  durable win; privacy enforcement often hurts readability. Default
  to monolith. Extract services when scaling profile, security
  domain, or team ownership genuinely diverges, not "to make
  testing faster."

## Testing

- `before(:all)` doing DB writes: transactional fixtures wrap
  each example, not context. Records leak. Use `let_it_be`
  (TestProf): `let_it_be(:user, reload: true)` /
  `refind: true` / `freeze: true`.
- `let!` everywhere: eager evaluation defeats laziness. Usually
  means the variable is used in every example; refactor to `before`
  or `let_it_be`.
- `expect_any_instance_of` is a design smell. Inject the
  collaborator instead.
- Always enable `verify_partial_doubles = true` and
  `verify_doubled_constant_names = true`.
- factory_bot: traits over factory proliferation (`:user` +
  `:admin`/`:active`, not `:admin_user`/`:active_admin_user`).
  `build_stubbed` is the right default for unit tests. `build`
  builds associations too (factory_bot 5+), unless the project sets
  `FactoryBot.use_parent_strategy = false`, which makes it `create`
  them.
  CI Rake task running `FactoryBot.lint` catches factory rot.
- 300+ system tests is a smell: pull variations down to
  request/model specs and keep ~15-30 happy-path smoke tests at
  system level. Cuprite (Ferrum/CDP) or
  capybara-playwright-driver (`:playwright`) over Selenium:
  faster and dramatically less flaky. Both expose race conditions
  Selenium was masking by being slow; fix in the test, not the
  driver: `expect(page).to have_css('.foo', text: 'bar')` over
  `find('.foo'); expect(page).to have_content('bar')`.
- Never `sleep`; use Capybara's auto-retrying matchers;
  `Capybara.disable_animation = true`; `js_errors: true` to fail on
  console errors loudly. Brittle CSS selector chains banned: use
  semantic locators (`click_on("Save")`, `fill_in("Email")`,
  role/aria queries, `data-testid` last-resort).
- WebMock: `WebMock.disable_net_connect!(allow_localhost: true)`.
  VCR for record/replay with
  `c.allow_http_connections_when_no_cassette = false` in CI.
- Order-dependent specs (`config.order = :defined`): always
  enable `:random` + `Kernel.srand config.seed`; bisect with
  `rspec --bisect`.
- `Timecop.freeze` without `Timecop.return`: time leaks. Use
  the block form `freeze_time { ... }`.

## Type checking

The 2025 convergence: RBS as the syntax in either engine.
Sorbet accepts inline RBS comments behind a flag; rbs-inline merged
into RBS 4.0. Inline `#:` annotations work in both ecosystems.

- Sorbet for large existing Rails monoliths (fast type-check,
  optional runtime checks). `# typed: false` minimum, `true` is the
  sweet spot, `strict` requires sigs on every method.
- Steep for OSS gems and below-megacorp scale codebases; Steep 1.9+
  added type guards, flow-sensitive typing, safe-nav narrowing.
- `T.untyped` / `untyped` is the biggest red flag: treat each
  like a TODO. Same for `T.must` / `T.cast` / `#: as !nil` as
  debugging crutches.
- `Hash[String, untyped]` smell: better as a typed struct,
  `T::Struct`, `Data.define`, or RBS record type.
- Tapioca DSL RBIs are auto-regenerated: hand edits go in
  `sorbet/rbi/shims/`.

## Gem ecosystem (high-leverage swaps)

| Out | In |
|---|---|
| `paranoia` / `acts_as_paranoid` | `discard` |
| `active_model_serializers` | `Alba` / `Blueprinter` / `Jbuilder` |
| `sprockets` / `webpacker` | `Propshaft` + importmap-rails / jsbundling |
| `delayed_job` / `resque` | `Solid Queue` / `GoodJob` / `Sidekiq` |
| `cancancan` | `Pundit` / `action_policy` |
| `paperclip` | `ActiveStorage` (+ `Shrine` for power users) |
| `httparty` / `rest-client` | `Faraday` / `HTTPX` |
| `kaminari` / `will_paginate` | `Pagy` |
| `virtus` | `ActiveModel::Attributes` / `dry-types` / `Data.define` |
| `reform` | `ActiveModel::Model` form objects |
| `dry-transaction` | `dry-monads` (Do notation) / `dry-operation` |

## Anti-patterns / red flags

- `where("col = '#{value}'")`: SQL interpolation.
- `Arel.sql(params[:sort])` without an allow-list.
- `redirect_to params[:next]` directly.
- `Model.find(params[:id])` outside a scoped query (IDOR).
- `params.require(:x).permit!`: mass-assignment open door.
- `.html_safe` / `raw` / `<%==` on user-controlled strings.
- `YAML.unsafe_load`, `Marshal.load`, or
  `JSON.parse(_, create_additions: true)` on untrusted data.
- `OpenStruct` for value objects;
  `Struct.new(..., keyword_init: true)` for read-only data.
- `def initialize(*args, **kwargs)` swallowing arbitrary input.
- `find_or_create_by` in a hot path with no unique index (race).
- `Model.first` / `Model.last` on an unordered scope.
- `Job.perform_later(user)` instead of `Job.perform_later(user_id)`.
- `class << self` with no instance methods: make it a module.
- `rescue => e` with no logging and no re-raise.
- `raise "message"` / `fail "message"` for recoverable domain
  outcomes; define a named exception or explicit result variant.
- `@result ||= compute` when `compute` may return `false`/`nil`.
- `Time.now` in domain logic; prefer `Time.current` or an injected
  clock. See [`domain-modeling/references/dates.md`](../../domain-modeling/references/dates.md)
  for the cross-language discipline.
- `BigDecimal`-less monetary math; mixing currencies. `money-rails`
  is the standard Rails pick. See
  [`domain-modeling/references/money.md`](../../domain-modeling/references/money.md).
- Brakeman without `--exit-on-warn`.
- Single-platform `Gemfile.lock`.
- `master.key` in git history.
- `config.hosts` empty in production.
- `before(:all) { create(...) }` in specs.
- `expect_any_instance_of(...)`.
- `sleep` in system specs.
- 300+ system tests (test-pyramid violation).

## Sources

- Rails Security Guide:
  <https://guides.rubyonrails.org/security.html>
- Active Record Querying / Eager Loading:
  <https://guides.rubyonrails.org/active_record_querying.html#eager-loading-associations>
- Ruby Style Guide: <https://rubystyle.guide/>
- Rails Style Guide: <https://rails.rubystyle.guide/>
- RuboCop docs: <https://docs.rubocop.org/>
- Brakeman: <https://brakemanscanner.org/docs/>
- Prosopite (N+1 detection): <https://github.com/charkost/prosopite>
- Pagy (pagination): <https://github.com/ddnexus/pagy>
- Hotwire / Turbo handbook: <https://turbo.hotwired.dev/handbook/>
- Stimulus reference: <https://stimulus.hotwired.dev/reference>
- Sorbet docs: <https://sorbet.org/docs/overview>
- RBS / Steep: <https://github.com/ruby/rbs> ·
  <https://github.com/soutaro/steep>
