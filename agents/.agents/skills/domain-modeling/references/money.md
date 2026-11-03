# Money and currency

Use this when storing, comparing, formatting, serializing, or computing on
monetary amounts. Loaded by `domain-modeling` Rule 8.

## Rules

1. Never hold money in a binary float (`float`, `double`, JS `Number`)
   anywhere in the chain, including JSON numbers that parse to floats. Use a
   decimal type or integer minor units.
2. An amount always travels beside its ISO 4217 code (`USD`, not `$`) in
   APIs, signatures, schemas, events, and cache keys. Many currencies share
   `$`, so symbols are display only. Comparing or adding amounts in
   different currencies fails, never coerces.
3. Minor units scale by the currency's exponent from maintained currency
   data, never a hardcoded `100`: JPY has 0 decimals, KWD and BHD have 3.
4. Pick one rounding mode, document it, and use it in every layer. The order
   of rounding, discounts, and tax (per line or per invoice) follows the
   product or tax spec.
5. Convert currency once, at the edge, and store the rate and its timestamp
   with the result. Never convert on every page load with a live rate, and
   never convert to a base currency in a way that loses the source currency.
6. Pick one sign convention for refunds and credits and use it everywhere.

## Defaults by layer

| Layer | Default |
|---|---|
| Wire | `{ "amount": "12.34", "currency": "USD" }` (a decimal string) or `{ "amount_minor": 1234, "currency": "USD" }`. Document which. |
| Database | Integer minor units plus a `currency` column, or `NUMERIC` with a documented scale plus a `currency` column. A value with more decimals than the scale is rounded silently. |
| Display | Locale-aware currency formatting at the UI edge only. |
