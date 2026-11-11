import assert from "node:assert/strict";
import test from "node:test";
import { describePayment, isChargeable, processingFeeCents, receiptLine } from "../src/payments.js";

const visa = { id: "pm_1", method: "card", cardBrand: "Visa", cardLast4: "4242", expMonth: 8, expYear: 2027 };

test("a card is described by brand and last four digits", () => {
  assert.equal(describePayment(visa), "Visa ending 4242");
});

test("a card can be charged through the end of its expiry month", () => {
  assert.equal(isChargeable(visa, "2027-08-31"), true);
  assert.equal(isChargeable(visa, "2027-09-01"), false);
});

test("the card fee is 2.9% plus 30 cents", () => {
  assert.equal(processingFeeCents(visa, 10000), 320);
});

test("a receipt line names the amount and the method", () => {
  assert.equal(receiptLine(visa, 1234), "Charged $12.34 to Visa ending 4242");
});
