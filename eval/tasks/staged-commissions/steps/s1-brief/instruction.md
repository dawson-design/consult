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
