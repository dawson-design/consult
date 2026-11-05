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
