## Turn 1: s1-brief

# Commissions service

We're Holloway Joinery, a small workshop that builds furniture to order.
Customers order pieces from our catalogue (`catalogue.json`), we build each
order by hand, then send it out with a carrier. We want a backend for our new
shop front. `GLOSSARY.md` has the words we use.

The shop front needs to:

- Place an order for one or more catalogue pieces: `POST /commissions` with
  `{"pieces": [{"design": "oak-bench", "quantity": 1}]}` answers 201 with the
  commission: its `id`, `status`, `pieces`, and `total`.
- Show an order: `GET /commissions/:id`.

Our workshop tool moves an order along, strictly in this order:

- `POST /commissions/:id/start` when we start building it.
- `POST /commissions/:id/dispatch` with `{"consignment": "..."}`, the
  carrier's consignment number, which the commission then shows.
- `POST /commissions/:id/deliver` when the carrier confirms delivery.

Store data in SQLite with Node's built-in `node:sqlite`, in the file named by
`DATABASE_PATH`. The server listens on `PORT`, and `npm start` runs it.

Work in the provided repository.

## Turn 2: s1-approve

Approved, including the interface and data shapes you proposed. Build it.
Use your recommended option for anything still open.

## Turn 3: s1-continue

Approved. Continue.

## Turn 4: s2-brief

# Cancelling an order

Customers want to cancel orders. They can cancel any time before we dispatch.
If we've already started building, they owe a restocking fee of 20% of the
total; before that, cancelling is free.

The shop front will call `POST /commissions/:id/withdrawal`, optionally with
`{"reason": "..."}`. Afterwards the commission shows the `reason` and the
`restockingFee`, in the same money format as `total`.

## Turn 5: s2-approve

Approved, including the interface and data shapes you proposed. Build it.
Use your recommended option for anything still open.

## Turn 6: s2-continue

Approved. Continue.

## Turn 7: s3-brief

# Customer accounts

Right now anyone can see any order. Customers need accounts, and should only
see their own orders.

- Sign up: `POST /patrons` with `{"email": "...", "password": "..."}` answers
  201. One account per email address.
- Log in: `POST /sessions` with the same fields answers 201 with
  `{"token": "..."}`.
- The shop front sends `Authorization: Bearer <token>` when it places, shows,
  lists, or cancels an order. Listing is new: `GET /commissions`. Customers
  only ever get their own orders.

The workshop tool's calls (start, dispatch, deliver) run on our internal
network and stay as they are. Orders placed before accounts existed can stay
without an owner.

## Turn 8: s3-approve

Approved, including the interface and data shapes you proposed. Build it.
Use your recommended option for anything still open.

## Turn 9: s3-continue

Approved. Continue.

## Turn 10: s4-brief

# Prices abroad

We're starting to sell into Europe and the US. When the shop front shows an
order it can ask for a currency: `GET /commissions/:id?currency=EUR`. We
support GBP (our own, and the default), EUR, and USD. The `total` is then in
that currency, and a `currency` field says which.

Exchange rates come from our FX provider:
`GET {RATES_URL}/rates?base=GBP` returns
`{"base": "GBP", "rates": {"EUR": 1.17, "USD": 1.27}}`. `RATES_URL` is set in
each environment.

## Turn 11: s4-approve

Approved, including the interface and data shapes you proposed. Build it.
Use your recommended option for anything still open.

## Turn 12: s4-continue

Approved. Continue.

## Turn 13: s5-brief

# Deposits

We're changing how customers pay. From now on a customer pays a 30% deposit
when they place an order, and the balance when we dispatch it. There's no
payment provider yet, so just record the amounts.

- A commission shows its `deposit` and `balanceDue`.
- Cancelling before we start building refunds the whole deposit. Cancelling
  after we've started keeps the restocking fee out of the deposit and refunds
  the rest. The commission then shows the `refund`.
- These amounts follow the requested currency, like `total`.

## Turn 14: s5-approve

Approved, including the interface and data shapes you proposed. Build it.
Use your recommended option for anything still open.

## Turn 15: s5-continue

Approved. Continue.
