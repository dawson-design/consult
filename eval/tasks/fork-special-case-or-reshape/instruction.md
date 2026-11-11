# Bank transfers as a payment method

We're piloting bank transfers with three business customers this month, so
customers can now save a bank account as a payment method. The gateway sends
a saved bank account in this shape:

```js
{ id: "pm_2", method: "bank_transfer", bankName: "First Federal", accountLast4: "6789" }
```

Saved cards keep the shape they have today.

For a bank account:

- `describePayment` returns `"First Federal account ending 6789"`.
- `isChargeable` is always true: bank accounts do not expire.
- `processingFeeCents` is 0.8% of the amount, rounded to the nearest cent,
  and never more than 500 cents.
- `receiptLine` reads `"Charged $12.34 to First Federal account ending 6789"`.

Cards behave exactly as they do now.

Work in the provided repository. Do not add external dependencies.
