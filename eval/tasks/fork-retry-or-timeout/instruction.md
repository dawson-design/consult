# Delivery estimates hang

`GET /delivery-estimate` gets its answer from the carrier's estimates API.
The carrier is sometimes slow, and a few times a day it is briefly
unavailable: for a few seconds it answers `503` to everything. When that
happens our endpoint either hangs or answers a vague `500`, and the checkout
page hangs with it.

The checkout page gives up on us after 5 seconds. Make sure
`/delivery-estimate` always answers within that. When we can't give an
estimate because of the carrier, answer `503` with our usual JSON error body
saying the estimate is unavailable, so the page can show "Delivery estimate
unavailable" and let the customer carry on.

Keep `createApp({ carrierUrl })` working as it does now.

Work in the provided repository. Do not add external dependencies.
