# Prices abroad

We're starting to sell into Europe and the US. When the shop front shows an
order it can ask for a currency: `GET /commissions/:id?currency=EUR`. We
support GBP (our own, and the default), EUR, and USD. The `total` is then in
that currency, and a `currency` field says which.

Exchange rates come from our FX provider:
`GET {RATES_URL}/rates?base=GBP` returns
`{"base": "GBP", "rates": {"EUR": 1.17, "USD": 1.27}}`. `RATES_URL` is set in
each environment.
