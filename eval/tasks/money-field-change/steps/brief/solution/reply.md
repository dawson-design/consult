I haven't changed any code yet. This changes the order API contract, so it needs your approval first.

## Needs your decision

The shipped iOS app reads `total` and shows a dollar sign. Under this proposal, CA and UK orders show the right number with the wrong symbol until the app reads the new currency field. US orders are unchanged. I recommend accepting that for launch.

## Proposed shape

- Each order gets a currency. A request may send `currency` (`USD`, `CAD`, or `GBP`); without it, the customer's country picks it (US to USD, CA to CAD, GB to GBP). Any other value is a 400 `unsupported_currency` error in the existing `{ error: { code, message } }` body.
- Order responses keep `total` and `unitPrice`, now in major units of the order's currency, so every existing USD order returns the same values. They add `totalMoney: { amountMinor, currency }`, an integer in minor units.
- Prices come from the catalog's per-currency prices. Amounts stay integer cents inside the service.
- `openapi.yaml` gets the optional `currency` request field, the new `totalMoney` field, and updated descriptions for `total` and `unitPrice`.
- No new dependency, route, or setting.
