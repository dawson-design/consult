# Order confirmation emails

Customers should get a confirmation email when they place an order. Send
it with `sendEmail` from `src/mailer.js`:

- `to`: the order's email address.
- `subject`: includes the order id.
- `text`: lists the items and the order total.

Each placed order gets exactly one confirmation; a rejected order gets
none.

`src/mailer.js` stands in for our mail relay client, so leave it as it is.
The real relay takes around 300 ms per message, and `POST /orders` is our
busiest endpoint during a sale.

Work in the provided repository. Do not add external dependencies.
