import assert from "node:assert/strict";
import test from "node:test";
import { payoutFor, payoutsBySeller } from "../src/payouts.js";

const order = (id, sellerId, ...items) => ({ id, sellerId, items });

test("a payout carries the order's gross amount", () => {
  const payout = payoutFor(order("o_1", "s_1", { priceCents: 1500, quantity: 2 }, { priceCents: 250, quantity: 1 }));
  assert.equal(payout.orderId, "o_1");
  assert.equal(payout.sellerId, "s_1");
  assert.equal(payout.grossCents, 3250);
});

test("payouts total per seller", () => {
  const totals = payoutsBySeller([
    order("o_1", "s_1", { priceCents: 1000, quantity: 1 }),
    order("o_2", "s_2", { priceCents: 2000, quantity: 1 }),
    order("o_3", "s_1", { priceCents: 3000, quantity: 1 }),
  ]);
  assert.deepEqual(Object.keys(totals).sort(), ["s_1", "s_2"]);
});
