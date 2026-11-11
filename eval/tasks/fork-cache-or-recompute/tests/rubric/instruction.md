# Category summary for the storefront

The storefront's new navigation bar shows each category with how many
products it has in stock and its lowest in-stock price. Add
`GET /catalog/summary` for it, answering:

```json
{
  "categories": [
    { "category": "home", "inStock": 2, "lowestPrice": 1500 }
  ]
}
```

- One entry per category that has at least one product in stock, sorted by
  category name.
- `inStock` counts the category's products in stock; `lowestPrice` is the
  lowest price among them, in pence like the catalog.

The navigation bar renders on every page view, so this endpoint will be
called far more often than anything else here: a few hundred times a second
at peak. Merchandising still edits `data/catalog.json` by hand during the
day, and an edit should show up on the site within a second, without a
restart.

Work in the provided repository. Do not add external dependencies.
