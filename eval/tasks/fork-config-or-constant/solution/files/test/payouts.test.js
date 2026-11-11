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

test("the platform fee is 2.9% of the gross, rounded to the nearest cent", () => {
  assert.equal(payoutFor(order("o_1", "s_1", { priceCents: 10000, quantity: 1 })).feeCents, 290);
  assert.equal(payoutFor(order("o_2", "s_1", { priceCents: 1234, quantity: 1 })).feeCents, 36);
  assert.equal(payoutFor(order("o_3", "s_1", { priceCents: 1250, quantity: 1 })).feeCents, 36);
});

test("the net amount is the gross minus the fee", () => {
  const payout = payoutFor(order("o_1", "s_1", { priceCents: 1234, quantity: 1 }));
  assert.equal(payout.netCents, 1234 - 36);
});

test("payouts total the net amounts per seller", () => {
  const totals = payoutsBySeller([
    order("o_1", "s_1", { priceCents: 10000, quantity: 1 }),
    order("o_2", "s_2", { priceCents: 2000, quantity: 1 }),
    order("o_3", "s_1", { priceCents: 1234, quantity: 1 }),
  ]);
  assert.deepEqual(totals, { s_1: 9710 + 1198, s_2: 2000 - 58 });
});
