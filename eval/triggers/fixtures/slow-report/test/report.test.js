import assert from "node:assert/strict";
import test from "node:test";
import { buildReport } from "../src/report.js";

test("rows are per customer, largest total first", () => {
  const customers = [{ id: 1, name: "Ada" }, { id: 2, name: "Bo" }];
  const orders = [
    { customerId: 1, sku: "a", totalCents: 500 },
    { customerId: 2, sku: "a", totalCents: 900 },
    { customerId: 2, sku: "b", totalCents: 100 },
  ];
  assert.deepEqual(buildReport(customers, orders), [
    { customer: "Bo", orders: 2, totalCents: 1000, distinctSkus: 2 },
    { customer: "Ada", orders: 1, totalCents: 500, distinctSkus: 1 },
  ]);
});
