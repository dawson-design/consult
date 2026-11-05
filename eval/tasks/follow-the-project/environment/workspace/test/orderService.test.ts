// OrderService business rules.
import assert from "node:assert/strict";
import test from "node:test";
import { ConflictError, ValidationError } from "../src/errors.ts";
import { OrderRepository } from "../src/repositories/orderRepository.ts";
import { OrderService } from "../src/services/orderService.ts";

const service = () => new OrderService(new OrderRepository());

test("an order is priced from the price list", () => {
  assert.equal(service().placeOrder([{ sku: "mug", quantity: 2 }]).totalPence, 1600);
});

test("unknown skus are rejected", () => {
  assert.throws(() => service().placeOrder([{ sku: "kettle", quantity: 1 }]), ValidationError);
});

test("payments cannot exceed the amount due", () => {
  const s = service();
  const order = s.placeOrder([{ sku: "mug", quantity: 1 }]);
  assert.throws(() => s.pay(order.id, 900), ConflictError);
});
