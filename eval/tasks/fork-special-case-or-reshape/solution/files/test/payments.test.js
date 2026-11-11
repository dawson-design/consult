import assert from "node:assert/strict";
import test from "node:test";
import { describePayment, isChargeable, processingFeeCents, receiptLine } from "../src/payments.js";

const visa = { id: "pm_1", method: "card", cardBrand: "Visa", cardLast4: "4242", expMonth: 8, expYear: 2027 };
const bank = { id: "pm_2", method: "bank_transfer", bankName: "First Federal", accountLast4: "6789" };

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
  assert.equal(receiptLine(bank, 1234), "Charged $12.34 to First Federal account ending 6789");
});

test("a bank account is described by bank and last four digits", () => {
  assert.equal(describePayment(bank), "First Federal account ending 6789");
});

test("a bank account never expires", () => {
  assert.equal(isChargeable(bank, "2099-12-31"), true);
});

test("the bank fee is 0.8%, rounded, and at most 500 cents", () => {
  assert.equal(processingFeeCents(bank, 10000), 80);
  assert.equal(processingFeeCents(bank, 1234), 10);
  assert.equal(processingFeeCents(bank, 62500), 500);
  assert.equal(processingFeeCents(bank, 1_000_000), 500);
});

test("an unknown method is rejected", () => {
  assert.throws(() => describePayment({ id: "pm_3", method: "cheque" }), RangeError);
});
