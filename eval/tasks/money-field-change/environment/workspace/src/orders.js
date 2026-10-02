import { catalog } from "./catalog.js";
import { customers } from "./customers.js";

export class OrderError extends Error {
  constructor(status, code, message) {
    super(message);
    this.status = status;
    this.code = code;
  }
}

const orders = new Map();
let nextId = 1;

function parseItems(items) {
  if (!Array.isArray(items) || items.length === 0) {
    throw new OrderError(400, "invalid_items", "items must be a non-empty array");
  }
  return items.map(({ sku, quantity }) => {
    if (!catalog[sku]) throw new OrderError(400, "unknown_sku", `unknown sku ${sku}`);
    if (!Number.isInteger(quantity) || quantity < 1) {
      throw new OrderError(400, "invalid_quantity", "quantity must be a positive integer");
    }
    return { sku, quantity, unitPriceCents: catalog[sku].prices.USD };
  });
}

export function createOrder({ customerId, items } = {}) {
  if (!customers[customerId]) throw new OrderError(400, "unknown_customer", "unknown customer");
  const lines = parseItems(items);
  const totalCents = lines.reduce((sum, line) => sum + line.unitPriceCents * line.quantity, 0);
  const order = { id: `o_${nextId++}`, customerId, status: "pending", items: lines, totalCents };
  orders.set(order.id, order);
  return order;
}

export function getOrder(id) {
  const order = orders.get(id);
  if (!order) throw new OrderError(404, "not_found", `order ${id} not found`);
  return order;
}

export function toResponse(order) {
  return {
    id: order.id,
    customerId: order.customerId,
    status: order.status,
    items: order.items.map(({ sku, quantity, unitPriceCents }) => ({ sku, quantity, unitPrice: unitPriceCents / 100 })),
    total: order.totalCents / 100,
  };
}
