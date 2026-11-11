// Hidden check for fork-config-or-constant: a 2.9% platform fee, rounded to the
// nearest cent, comes off every payout. Either side of the fork passes: a
// constant, or a setting that defaults to 2.9% when nothing sets it.
import assert from "node:assert/strict";
import { payoutFor, payoutsBySeller } from "./src/payouts.js";

const order = (id, sellerId, ...items) => ({ id, sellerId, items });

const cases = [
  [10000, 290],
  [1234, 36], // 35.786
  [1250, 36], // 36.25
  [3150, 91], // 91.35
  [4000, 116],
  [0, 0],
];
for (const [grossCents, feeCents] of cases) {
  const payout = payoutFor(order("o_1", "s_1", { priceCents: grossCents, quantity: 1 }));
  assert.equal(payout.grossCents, grossCents, `gross for ${grossCents}`);
  assert.equal(payout.feeCents, feeCents, `fee for ${grossCents}`);
  assert.equal(payout.netCents, grossCents - feeCents, `net for ${grossCents}`);
}

const payout = payoutFor(order("o_9", "s_9", { priceCents: 1500, quantity: 2 }, { priceCents: 250, quantity: 4 }));
assert.equal(payout.orderId, "o_9");
assert.equal(payout.sellerId, "s_9");
assert.equal(payout.grossCents, 4000);
assert.equal(payout.feeCents, 116);

assert.deepEqual(
  payoutsBySeller([
    order("o_1", "s_1", { priceCents: 10000, quantity: 1 }),
    order("o_2", "s_2", { priceCents: 3150, quantity: 1 }),
    order("o_3", "s_1", { priceCents: 1234, quantity: 1 }),
  ]),
  { s_1: 9710 + 1198, s_2: 3150 - 91 },
);
