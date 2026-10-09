# Money and currency

Use this when storing, comparing, formatting, serialising, or computing
on monetary amounts: at the language, wire, database, or display
layer. Loaded by `domain-modeling` Rule 11.

## Iron rules

1. **Never use binary floats.** `0.1 + 0.2 == 0.3` is `False`. Use
   `Decimal` / `BigDecimal` / fixed-point integer minor units.
   `float` / `double` / `Number` for money is a Critical-tier
   finding regardless of how "small" the application looks today.
2. Amount and currency travel together. A bare number is not
   money: `Money(amount, currency)` is. APIs, function signatures,
   DB schemas, and event payloads all carry both.
3. ISO 4217 codes (3-letter, uppercase). `USD`, `EUR`, `JPY`:
   not `$`, `€`, `¥`. Symbols are display-layer only; codes are the
   stored / wire identity.
4. Convert at the boundary, with a recorded rate. Mid-calculation
   conversion silently mixes units; later auditing can't reconstruct
   what happened. Convert once at the edge and persist the rate plus
   the conversion timestamp.
5. Pick a rounding policy and document it. Banker's rounding
   (half-to-even, financial default), half-up, half-down: all are
   valid; silent inconsistency between layers is not.

## Storage / wire / display

| Layer | Default |
|---|---|
| Database | Two columns: `amount_minor BIGINT NOT NULL` (integer minor units, e.g. cents) plus `currency CHAR(3) NOT NULL`. Or `NUMERIC(19, 4)` with a documented scale and the currency column. Never `FLOAT` / `REAL` / `DOUBLE PRECISION`. Add a check constraint on the currency column. |
| Wire / API | Object form: `{ "amount": "12.34", "currency": "USD" }` (string for the amount preserves precision across JSON's float). Or `{ "amount_minor": 1234, "currency": "USD" }` for an explicit minor-unit contract. Document which one. |
| Domain code | A `Money` value object that bundles amount and currency, rejects mixed-currency arithmetic, and uses `Decimal` / `BigDecimal` internally. Most ecosystems have one (`py-moneyed`, `joda-money`, `Money.gem`, `Stripe.Money`); reach for it before rolling your own. |
| Display | Locale-aware formatting at the UI edge: `Intl.NumberFormat(locale, { style: "currency", currency })`, ICU, `Locale.format`. The DB never sees `"$1,234.56"`; the user never sees `"123456 USD"`. |

## Per-currency decimal places

| Currency | Decimals |
|---|---|
| JPY, KRW, VND | 0 |
| USD, EUR, GBP, CAD, AUD | 2 |
| BHD, JOD, KWD, OMR, TND | 3 |
| CLF, UYW | 4 |

Do not hardcode "2 decimals" anywhere. Use the currency's
`exponent`/`fraction_digits` from ISO 4217. JPY at "2 decimals"
(`¥1234.00`) is wrong; KWD at "2 decimals" (`KD 12.34`) is missing a
significant digit.

## High-signal review checks

- Any `float` / `double` / JS `Number` holding money. Walk the call
  graph: once a float is in the chain, you've already lost
  precision.
- Mixed-currency arithmetic with no conversion: `USD + EUR` should
  fail at the type level, not silently coerce.
- A `price * tax_rate` followed by `round` for the line total:
  per-line rounding rules are jurisdiction-specific. Round per line,
  then sum. (Exception: VAT regimes that round at the invoice
  total.)
- Storing `1234.567` in a `NUMERIC(19, 2)` column: the database
  silently truncates to `1234.57` (or 56, depending on policy).
- Storing the symbol `"$"` instead of the code `"USD"`. Australian
  dollars, Canadian dollars, US dollars, Mexican pesos, Chilean
  pesos, and several others all share `$`.
- A discount or fee computed as a percentage with `Decimal` but
  truncated to integer cents at the wrong moment: verify the order
  of operations matches the regulatory or product spec.
- Currency conversion in a service method without persisting the
  rate or the conversion timestamp. Reconciliation needs both.
- Caching a "USD" price across regions because the codebase forgot a
  currency exists.
- Free-fall conversion: a "preferred display currency" feature that
  converts on every page load with the live rate: leads to flicker,
  reconciliation drift, and tax problems.
- "Round-trip safe" tests that assume `Decimal("0.1") + Decimal("0.2") == Decimal("0.3")`
  hold across formatters/parsers: most do, but JSON via `float`
  silently doesn't.
- Negative amounts: a refund is not a "credit" type: pick a sign
  convention and use it consistently. Mixed sign conventions across
  modules cause double-counting.

## Anti-patterns / red flags

- `price: float` / `amount: number` / `cost: double` in any API,
  schema, or domain class.
- `JSON.stringify({ price: 12.34 })` going through `Number` in a
  language that defaults to IEEE 754 (most).
- `total = sum(prices)` where `prices` is `list[float]`.
- `format(amount, "$%.2f")`: embedding the symbol in code.
- `if amount > other_amount` where the two amounts may be different
  currencies.
- A migration adding `price NUMERIC(10, 2)` with no `currency`
  column.
- Converting "to USD for storage" silently: the source currency is
  lost.
- Hardcoded `100` (cents per major unit) in the conversion: works
  for USD, breaks for JPY (1) and BHD (1000).
- A feature flag that switches a price between currencies without
  also switching the locale formatting.

## Sources

- ISO 4217 currency codes: <https://www.iso.org/iso-4217-currency-codes.html>
- "Falsehoods programmers believe about prices":
  <https://gist.github.com/rgs/6509585>
- Martin Fowler, "Money pattern":
  <https://martinfowler.com/eaaCatalog/money.html>
- Stripe API "Money handling":
  <https://stripe.com/docs/api/charges/object#charge_object-amount>
- PostgreSQL `NUMERIC`:
  <https://www.postgresql.org/docs/current/datatype-numeric.html>
- ICU number/currency formatting:
  <https://unicode-org.github.io/icu/userguide/format_parse/numbers/>
