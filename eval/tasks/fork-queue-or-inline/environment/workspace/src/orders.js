import { randomUUID } from "node:crypto";

const PRICES = { "MUG-01": 1200, "BWL-01": 2400, "CDL-01": 1500, "NTB-01": 1100 };
const orders = new Map();

// Returns { order } for a valid request, or { error } saying what is wrong with it.
export function placeOrder({ email, items } = {}) {
  if (typeof email !== "string" || !email.includes("@")) return { error: "email is required" };
  if (!Array.isArray(items) || items.length === 0) return { error: "items are required" };
  const unknown = items.find((item) => !(item.sku in PRICES) || !Number.isInteger(item.quantity) || item.quantity < 1);
  if (unknown) return { error: `invalid item ${JSON.stringify(unknown)}` };
  const total = items.reduce((sum, item) => sum + PRICES[item.sku] * item.quantity, 0);
  const order = { id: randomUUID(), email, items, total };
  orders.set(order.id, order);
  return { order };
}

export function findOrder(id) {
  return orders.get(id);
}
