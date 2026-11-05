# Gift cards

We want to sell gift cards. Staff issue a card with a starting balance:
`POST /gift-cards` with `{"balancePence": 5000}` answers 201 with the card's
`code` and `balancePence`.

Customers spend a card against an order:
`POST /orders/:id/gift-card-payments` with `{"code": "...", "amountPence": 2000}`
takes the amount off the card, counts it as paid on the order, and answers 201
with the card's remaining `balancePence`. A card can't go below zero, and it
can't pay more than the order still owes.

Work in the provided repository.
