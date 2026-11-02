# Order Discount Rules

`src/orders.js` exports `processOrder(order)`. It currently validates the
order, looks up SKU prices, applies a 10% tier discount on subtotals at or
above 5000 cents, charges the customer, and queues a confirmation email.

Extend it so the discount calculation also supports:

- Coupon `WELCOME`: a flat 500 cents off, stacking with any tier discount.
- The combined discount must never exceed the subtotal.

The order shape:

- `id`: string
- `email`: string
- `coupon`: string or absent
- `lines`: array of `{ sku, quantity }`

`processOrder` returns `{ ok, subtotal, discount, total }` on success or
`{ ok: false, error }` on validation failure.

Add tests that prove the discount rules across the supported cases and
that a successful order records the right charge and queues the right
confirmation email.

Do not add external dependencies.

Work in the provided repository. Do not add external dependencies.
