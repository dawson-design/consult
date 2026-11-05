# Deposits

We're changing how customers pay. From now on a customer pays a 30% deposit
when they place an order, and the balance when we dispatch it. There's no
payment provider yet, so just record the amounts.

- A commission shows its `deposit` and `balanceDue`.
- Cancelling before we start building refunds the whole deposit. Cancelling
  after we've started keeps the restocking fee out of the deposit and refunds
  the rest. The commission then shows the `refund`.
- These amounts follow the requested currency, like `total`.
