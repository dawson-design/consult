# Order service

Creates and serves storefront orders. The contract is `openapi.yaml`.

The iOS app (v3, in the App Store) reads `GET /orders/{id}` and shows `total`.

## Run

    npm start        # listens on $PORT, default 3000

## Test

    npm test
