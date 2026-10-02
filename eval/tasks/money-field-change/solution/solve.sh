#!/bin/bash
# Oracle for the build step: keep `total` (dollars) for USD callers, add
# totalMoney {amountMinor, currency} for every order, and choose the currency
# from an explicit field or the customer's country.
set -euo pipefail
cd /app
python3 - <<'PY'
from pathlib import Path

orders = Path("src/orders.js")
s = orders.read_text()
s = s.replace('''const orders = new Map();''', '''const CURRENCY_BY_COUNTRY = { US: "USD", CA: "CAD", GB: "GBP" };
const SUPPORTED = new Set(Object.values(CURRENCY_BY_COUNTRY));

const orders = new Map();''')
s = s.replace('''function parseItems(items) {''', '''function parseCurrency(currency, customer) {
  const chosen = currency ?? CURRENCY_BY_COUNTRY[customer.country];
  if (typeof chosen !== "string" || !SUPPORTED.has(chosen)) {
    throw new OrderError(400, "unsupported_currency", "currency must be one of USD, CAD, GBP");
  }
  return chosen;
}

function parseItems(items, currency) {''')
s = s.replace("unitPriceCents: catalog[sku].prices.USD", "unitPriceCents: catalog[sku].prices[currency]")
s = s.replace('''export function createOrder({ customerId, items } = {}) {
  if (!customers[customerId]) throw new OrderError(400, "unknown_customer", "unknown customer");
  const lines = parseItems(items);''', '''export function createOrder({ customerId, items, currency } = {}) {
  if (!customers[customerId]) throw new OrderError(400, "unknown_customer", "unknown customer");
  const orderCurrency = parseCurrency(currency, customers[customerId]);
  const lines = parseItems(items, orderCurrency);''')
s = s.replace('''const order = { id: `o_${nextId++}`, customerId, status: "pending", items: lines, totalCents };''',
              '''const order = { id: `o_${nextId++}`, customerId, status: "pending", currency: orderCurrency, items: lines, totalCents };''')
s = s.replace('''    total: order.totalCents / 100,
  };''', '''    total: order.totalCents / 100,
    totalMoney: { amountMinor: order.totalCents, currency: order.currency },
  };''')
orders.write_text(s)

spec = Path("openapi.yaml")
t = spec.read_text()
t = t.replace('''        total: { type: number, description: Order total in dollars }''', '''        total: { type: number, description: "Order total in major units of the order currency (dollars for USD orders)" }
        totalMoney:
          type: object
          required: [amountMinor, currency]
          properties:
            amountMinor: { type: integer, description: Total in minor units }
            currency: { type: string, enum: [USD, CAD, GBP] }''')
t = t.replace('''        customerId: { type: string }
        items:
          type: array
          minItems: 1''', '''        customerId: { type: string }
        currency: { type: string, enum: [USD, CAD, GBP], description: Defaults from the customer's country }
        items:
          type: array
          minItems: 1''')
spec.write_text(t)
PY
cat > test/currency.test.js <<'JS'
import test from "node:test";
import assert from "node:assert/strict";
import { createServer } from "../src/server.js";

test("CAD orders carry a CAD minor-unit total and USD keeps total", async () => {
  const server = createServer().listen(0);
  await new Promise((resolve) => server.once("listening", resolve));
  const base = `http://127.0.0.1:${server.address().port}`;
  const post = (body) => fetch(`${base}/orders`, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(body) });
  try {
    const cad = await (await post({ customerId: "c_ca", items: [{ sku: "sku-mug", quantity: 1 }] })).json();
    assert.deepEqual(cad.totalMoney, { amountMinor: 1600, currency: "CAD" });
    const usd = await (await post({ customerId: "c_us", items: [{ sku: "sku-mug", quantity: 1 }] })).json();
    assert.equal(usd.total, 12);
    assert.equal((await post({ customerId: "c_us", items: [{ sku: "sku-mug", quantity: 1 }], currency: "XYZ" })).status, 400);
  } finally {
    server.close();
  }
});
JS
