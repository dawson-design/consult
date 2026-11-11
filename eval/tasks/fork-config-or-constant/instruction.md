# Platform fee on payouts

Starting next month we keep a platform fee on every seller payout. For now
the fee is 2.9% of the order's gross amount, rounded to the nearest cent.
Finance is still negotiating the rate with our payment processor and expects
it to change at least once before the end of the quarter.

- `payoutFor` returns the fee as `feeCents`, and `netCents` becomes the gross
  amount minus the fee.
- `payoutsBySeller` keeps totalling the net amounts per seller.

Work in the provided repository. Do not add external dependencies.
