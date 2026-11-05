// GiftCardService business rules.
import assert from "node:assert/strict";
import test from "node:test";
import { ConflictError } from "../src/errors.ts";
import { GiftCardRepository } from "../src/repositories/giftCardRepository.ts";
import { OrderRepository } from "../src/repositories/orderRepository.ts";
import { GiftCardService } from "../src/services/giftCardService.ts";
import { OrderService } from "../src/services/orderService.ts";

function setup() {
  const orders = new OrderService(new OrderRepository());
  return { orders, cards: new GiftCardService(new GiftCardRepository(), orders) };
}

test("paying from a card lowers its balance and pays the order", () => {
  const { orders, cards } = setup();
  const order = orders.placeOrder([{ sku: "mug", quantity: 4 }]);
  const card = cards.issue(5000);
  assert.equal(cards.payOrder(order.id, card.code, 2000).balancePence, 3000);
  assert.equal(orders.getOrder(order.id).paidPence, 2000);
});

test("a card cannot go below zero", () => {
  const { orders, cards } = setup();
  const order = orders.placeOrder([{ sku: "mug", quantity: 4 }]);
  assert.throws(() => cards.payOrder(order.id, cards.issue(500).code, 1000), ConflictError);
});

test("a card cannot pay more than the order owes", () => {
  const { orders, cards } = setup();
  const order = orders.placeOrder([{ sku: "mug", quantity: 1 }]);
  const card = cards.issue(5000);
  assert.throws(() => cards.payOrder(order.id, card.code, 900), ConflictError);
  assert.equal(card.balancePence, 5000);
});
