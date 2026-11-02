#!/bin/bash
# Oracle: split the discount into a pure calculateDiscount (10% tier at 5000+,
# WELCOME 500 off stacking, combined discount capped at the subtotal), keep
# validation and pricing ahead of any effect, and let callers pass the charge
# and email effects so tests can see them. processOrder(order) still works
# with one argument and records into the module's own lists by default.
set -euo pipefail
cd /app
cat > src/orders.js <<'JS'
const PRICES = new Map([
  ["sku_1", 1000],
  ["sku_2", 2500],
  ["sku_3", 4500],
]);

const TIER_THRESHOLD_CENTS = 5000;
const TIER_RATE = 0.10;
const WELCOME_COUPON = "WELCOME";
const WELCOME_DISCOUNT_CENTS = 500;

const charges = [];
const emails = [];

const moduleEffects = {
  recordCharge: (charge) => charges.push(charge),
  queueEmail: (email) => emails.push(email),
};

function tierDiscount(subtotal) {
  return subtotal >= TIER_THRESHOLD_CENTS ? Math.floor(subtotal * TIER_RATE) : 0;
}

function couponDiscount(coupon) {
  return coupon === WELCOME_COUPON ? WELCOME_DISCOUNT_CENTS : 0;
}

// The tier and coupon discounts stack, and together never exceed the subtotal.
export function calculateDiscount(subtotal, coupon) {
  return Math.min(tierDiscount(subtotal) + couponDiscount(coupon), subtotal);
}

function priceLines(lines) {
  let subtotal = 0;
  for (const line of lines) {
    const price = PRICES.get(line.sku);
    if (price === undefined) {
      return { ok: false, error: "unknown sku: " + line.sku };
    }
    subtotal += price * line.quantity;
  }
  return { ok: true, subtotal };
}

function hasLines(order) {
  return Boolean(order) && Array.isArray(order.lines) && order.lines.length > 0;
}

// `effects` defaults to the module's own charge and email lists; tests pass
// recorders to see exactly what a successful order produces.
export function processOrder(order, effects = moduleEffects) {
  if (!hasLines(order)) {
    return { ok: false, error: "empty order" };
  }
  const priced = priceLines(order.lines);
  if (!priced.ok) return priced;
  const subtotal = priced.subtotal;
  const discount = calculateDiscount(subtotal, order.coupon);
  const total = subtotal - discount;
  effects.recordCharge({ orderId: order.id, amountCents: total });
  effects.queueEmail({
    to: order.email,
    subject: "Order " + order.id + " confirmed",
    amountCents: total,
  });
  return { ok: true, subtotal, discount, total };
}
JS
sed -i 's|^import { processOrder } from "../src/orders.js";$|import { calculateDiscount, processOrder } from "../src/orders.js";|' test/orders.test.js
cat >> test/orders.test.js <<'JS'

function recorder() {
  const charges = [];
  const emails = [];
  return {
    charges,
    emails,
    effects: {
      recordCharge: (charge) => charges.push(charge),
      queueEmail: (email) => emails.push(email),
    },
  };
}

function order(extra) {
  return { id: "o_7", email: "buyer@example.com", ...extra };
}

test("no discount below the 5000-cent tier without a coupon", () => {
  const result = processOrder(order({ lines: [{ sku: "sku_2", quantity: 1 }] }), recorder().effects);
  assert.deepEqual(result, { ok: true, subtotal: 2500, discount: 0, total: 2500 });
});

test("the 10% tier discount starts at exactly 5000 cents", () => {
  assert.equal(calculateDiscount(4999, undefined), 0);
  assert.equal(calculateDiscount(5000, undefined), 500);
});

test("the tier discount alone is 10% of a 9000-cent subtotal", () => {
  const result = processOrder(order({ lines: [{ sku: "sku_3", quantity: 2 }] }), recorder().effects);
  assert.deepEqual(result, { ok: true, subtotal: 9000, discount: 900, total: 8100 });
});

test("WELCOME takes a flat 500 cents off below the tier", () => {
  const result = processOrder(order({ coupon: "WELCOME", lines: [{ sku: "sku_1", quantity: 1 }] }), recorder().effects);
  assert.deepEqual(result, { ok: true, subtotal: 1000, discount: 500, total: 500 });
});

test("WELCOME stacks with the tier discount", () => {
  const result = processOrder(order({ coupon: "WELCOME", lines: [{ sku: "sku_3", quantity: 2 }] }), recorder().effects);
  assert.deepEqual(result, { ok: true, subtotal: 9000, discount: 1400, total: 7600 });
});

test("an unknown coupon gives no coupon discount", () => {
  assert.equal(calculateDiscount(1000, "SUMMER"), 0);
});

test("the combined discount never exceeds the subtotal", () => {
  assert.equal(calculateDiscount(300, "WELCOME"), 300);
  const result = processOrder(order({ coupon: "WELCOME", lines: [{ sku: "sku_1", quantity: 0 }] }), recorder().effects);
  assert.deepEqual(result, { ok: true, subtotal: 0, discount: 0, total: 0 });
});

test("a successful order charges and emails the discounted total", () => {
  const { charges, emails, effects } = recorder();
  processOrder(order({ coupon: "WELCOME", lines: [{ sku: "sku_3", quantity: 2 }] }), effects);
  assert.deepEqual(charges, [{ orderId: "o_7", amountCents: 7600 }]);
  assert.deepEqual(emails, [{ to: "buyer@example.com", subject: "Order o_7 confirmed", amountCents: 7600 }]);
});

test("a failed order is neither charged nor emailed", () => {
  const { charges, emails, effects } = recorder();
  assert.deepEqual(processOrder(order({ lines: [] }), effects), { ok: false, error: "empty order" });
  assert.deepEqual(processOrder(order({ coupon: "WELCOME", lines: [{ sku: "sku_9", quantity: 1 }] }), effects), {
    ok: false,
    error: "unknown sku: sku_9",
  });
  assert.deepEqual(charges, []);
  assert.deepEqual(emails, []);
});
JS
