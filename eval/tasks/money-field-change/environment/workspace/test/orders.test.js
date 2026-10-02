import test from "node:test";
import assert from "node:assert/strict";
import { createServer } from "../src/server.js";

async function withServer(fn) {
  const server = createServer().listen(0);
  await new Promise((resolve) => server.once("listening", resolve));
  const base = `http://127.0.0.1:${server.address().port}`;
  try {
    await fn(base);
  } finally {
    server.close();
  }
}

const post = (base, body) =>
  fetch(`${base}/orders`, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(body) });

test("creates and reads an order with a dollar total", () =>
  withServer(async (base) => {
    const created = await post(base, { customerId: "c_us", items: [{ sku: "sku-mug", quantity: 2 }] });
    assert.equal(created.status, 201);
    const order = await (await fetch(`${base}/orders/${(await created.json()).id}`)).json();
    assert.equal(order.total, 24);
    assert.equal(order.items[0].unitPrice, 12);
  }));

test("rejects bad input and unknown orders", () =>
  withServer(async (base) => {
    assert.equal((await post(base, { customerId: "c_us", items: [] })).status, 400);
    assert.equal((await fetch(`${base}/orders/o_missing`)).status, 404);
  }));
