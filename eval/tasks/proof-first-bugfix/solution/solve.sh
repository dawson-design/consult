#!/bin/bash
# Oracle reference solution for proof-first-bugfix.
set -euo pipefail
cd /app
cat > src/cart.js <<'JS'
export function totalCents(items, discountCode) {
  if (!Array.isArray(items)) {
    throw new TypeError("items must be an array");
  }
  const subtotal = items.reduce((sum, item, index) => {
    if (!item || typeof item !== "object") {
      throw new TypeError(`item at index ${index} must be an object`);
    }
    if (!Number.isInteger(item.priceCents) || item.priceCents < 0) {
      throw new RangeError(`item at index ${index} has invalid priceCents`);
    }
    if (!Number.isInteger(item.quantity) || item.quantity < 1) {
      throw new RangeError(`item at index ${index} has invalid quantity`);
    }
    return sum + item.priceCents * item.quantity;
  }, 0);
  if (discountCode == null) {
    return subtotal;
  }
  if (discountCode !== "SAVE10") {
    throw new RangeError("unsupported discount code");
  }
  return Math.round(subtotal * 0.9);
}
JS
cat > test/cart.test.js <<'JS'
import assert from "node:assert/strict";
import test from "node:test";
import { totalCents } from "../src/cart.js";

test("totals item prices in cents", () => {
  assert.equal(
    totalCents([
      { priceCents: 500, quantity: 2 },
      { priceCents: 125, quantity: 1 },
    ]),
    1125,
  );
});

test("applies SAVE10 and returns the final total in cents", () => {
  assert.equal(totalCents([{ priceCents: 500, quantity: 2 }], "SAVE10"), 900);
  assert.equal(totalCents([{ priceCents: 333, quantity: 3 }], "SAVE10"), 899);
});

test("rejects malformed carts", () => {
  assert.throws(() => totalCents(null), /items must be an array/);
  assert.throws(() => totalCents([null]), /item at index 0 must be an object/);
});

test("rejects invalid item values and unsupported discount codes", () => {
  assert.throws(() => totalCents([{ priceCents: -1, quantity: 1 }]), /invalid priceCents/);
  assert.throws(() => totalCents([{ priceCents: 100, quantity: 0 }]), /invalid quantity/);
  assert.throws(() => totalCents([{ priceCents: 100, quantity: 1 }], "BOGUS"), /unsupported discount code/);
});
JS
npm test
