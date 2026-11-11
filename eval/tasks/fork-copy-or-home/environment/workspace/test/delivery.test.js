import assert from "node:assert/strict";
import test from "node:test";
import { estimateDelivery } from "../src/delivery.js";

test("standard delivery takes five business days", () => {
  assert.equal(estimateDelivery({ placedOn: "2026-03-02", shipping: "standard" }), "2026-03-09");
});

test("express delivery skips the weekend", () => {
  assert.equal(estimateDelivery({ placedOn: "2026-03-05", shipping: "express" }), "2026-03-09");
});

test("company holidays are not business days", () => {
  assert.equal(estimateDelivery({ placedOn: "2026-11-24", shipping: "express" }), "2026-11-27");
});
