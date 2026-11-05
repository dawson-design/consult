# Cancelling an order

Customers want to cancel orders. They can cancel any time before we dispatch.
If we've already started building, they owe a restocking fee of 20% of the
total; before that, cancelling is free.

The shop front will call `POST /commissions/:id/withdrawal`, optionally with
`{"reason": "..."}`. Afterwards the commission shows the `reason` and the
`restockingFee`, in the same money format as `total`.
