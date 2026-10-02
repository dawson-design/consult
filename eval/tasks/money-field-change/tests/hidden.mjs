// Hidden check: the shipped USD contract still holds and orders carry their total in
// their own currency. Any unit or form passes here; the money-representation rule
// is scored separately as domain-modeling.11 by the rules probe.
import assert from "node:assert/strict";
import { createServer } from "./src/server.js";

const items = [{ sku: "sku-mug", quantity: 1 }, { sku: "sku-tee", quantity: 1 }];

function hasMoney(value, currency, amounts) {
  if (!value || typeof value !== "object") return false;
  const entries = Object.entries(value);
  const currencyMatch = entries.some(([k, v]) => /currency/i.test(k) && v === currency);
  const amountMatch = entries.some(([k, v]) => /amount|minor|cents|value|total/i.test(k) && amounts.includes(v));
  return (currencyMatch && amountMatch) || Object.values(value).some((v) => hasMoney(v, currency, amounts));
}

async function createIn(base, customerId, currency) {
  for (const body of [{ customerId, items, currency }, { customerId, items }]) {
    const res = await fetch(`${base}/orders`, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(body) });
    if (res.status === 201) return res.json();
  }
  throw new Error(`could not create a ${currency} order`);
}

const server = createServer().listen(0);
await new Promise((resolve) => server.once("listening", resolve));
const base = `http://127.0.0.1:${server.address().port}`;
try {
  const usd = await createIn(base, "c_us", "USD");
  const read = await (await fetch(`${base}/orders/${usd.id}`)).json();
  assert.equal(read.total, 37);
  assert.equal(typeof read.items[0].unitPrice, "number");
  for (const [customer, currency, minor] of [["c_ca", "CAD", 4900], ["c_gb", "GBP", 2940]]) {
    const order = await createIn(base, customer, currency);
    const body = await (await fetch(`${base}/orders/${order.id}`)).json();
    const amounts = [minor, minor / 100, (minor / 100).toFixed(2), String(minor / 100)];
    assert.ok(hasMoney(body, currency, amounts), `${currency} order lacks a ${currency} total: ${JSON.stringify(body)}`);
  }
  const bad = await fetch(`${base}/orders`, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ customerId: "c_us", items: [] }) });
  assert.equal(bad.status, 400);
  assert.equal((await fetch(`${base}/orders/o_missing`)).status, 404);
} finally {
  server.close();
}
