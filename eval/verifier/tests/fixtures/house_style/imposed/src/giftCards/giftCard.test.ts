import assert from "node:assert/strict";
import test from "node:test";
import { spend } from "./giftCard.ts";

test("spending lowers the balance", () => {
  const spent = spend({ code: "a", balancePence: 500 }, 200);
  assert.ok(spent.ok && spent.value.balancePence === 300);
});
