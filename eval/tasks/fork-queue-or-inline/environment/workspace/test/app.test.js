import assert from "node:assert/strict";
import { after, before, test } from "node:test";
import { createApp } from "../src/app.js";

let app;
let base;

before(async () => {
  app = createApp();
  await new Promise((resolve) => app.listen(0, "127.0.0.1", resolve));
  base = `http://127.0.0.1:${app.address().port}`;
});

after(() => app.close());

function post(body) {
  return fetch(`${base}/orders`, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(body) });
}

test("places an order and totals it", async () => {
  const response = await post({ email: "ada@example.com", items: [{ sku: "MUG-01", quantity: 2 }] });
  assert.equal(response.status, 201);
  const order = await response.json();
  assert.equal(order.total, 2400);
  const fetched = await fetch(`${base}/orders/${order.id}`);
  assert.deepEqual(await fetched.json(), order);
});

test("rejects an order without items", async () => {
  const response = await post({ email: "ada@example.com", items: [] });
  assert.equal(response.status, 400);
});
