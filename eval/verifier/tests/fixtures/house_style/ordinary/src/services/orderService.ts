import { DatabaseSync } from "node:sqlite";
import type { Order } from "../models/order.ts";
import { OrderError } from "../models/order.ts";
import { createHash } from "node:crypto";

export class OrderService {
  private db: DatabaseSync;
  private cache: Map<string, Order> = new Map();
  constructor(path: string) { this.db = new DatabaseSync(path); }
  cancelOrder(id: string, reason: string | null): Order {
    const order = this.getOrder(id);
    if (order.status === "dispatched" || order.status === "delivered") {
      throw new OrderError(409, "cannot cancel");
    }
    if (order.status === "cancelled") {
      throw new OrderError(409, "already cancelled");
    }
    let fee = 0;
    if (order.status === "in_progress") {
      fee = Math.round(order.total * 0.2);
    }
    order.status = "cancelled";
    order.isCancelled = true;
    order.cancelReason = reason;
    order.restockingFee = fee;
    this.db.prepare("UPDATE orders SET status = ?, restocking_fee = ? WHERE id = ?").run("cancelled", fee, id);
    this.cache.set(id, order);
    return order;
  }
  getOrder(id: string): Order {
    const row = this.db.prepare("SELECT * FROM orders WHERE id = ?").get(id) as Order | undefined;
    if (!row) throw new OrderError(404, "not found");
    return row;
  }
  processSignup(email: string, password: string) {
    const existing = this.db.prepare("SELECT id FROM customers WHERE email = ?").get(email);
    if (existing) throw new OrderError(409, "taken");
    const hash = createHash("sha256").update(password).digest("hex");
    this.db.prepare("INSERT INTO customers (email, password) VALUES (?, ?)").run(email, hash);
  }
}
