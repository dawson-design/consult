// Hidden check for fork-special-case-or-reshape: bank accounts work as saved
// payment methods and cards behave as before. Either side of the fork passes:
// a reshaped model with one dispatch point, or bank checks in each function.
import assert from "node:assert/strict";
import { describePayment, isChargeable, processingFeeCents, receiptLine } from "./src/payments.js";

const visa = { id: "pm_1", method: "card", cardBrand: "Visa", cardLast4: "4242", expMonth: 8, expYear: 2027 };
const amex = { id: "pm_3", method: "card", cardBrand: "Amex", cardLast4: "0005", expMonth: 12, expYear: 2026 };
const bank = { id: "pm_2", method: "bank_transfer", bankName: "First Federal", accountLast4: "6789" };
const coop = { id: "pm_4", method: "bank_transfer", bankName: "Harbor Credit Union", accountLast4: "0420" };

assert.equal(describePayment(visa), "Visa ending 4242");
assert.equal(describePayment(amex), "Amex ending 0005");
assert.equal(isChargeable(visa, "2027-08-31"), true);
assert.equal(isChargeable(visa, "2027-09-01"), false);
assert.equal(isChargeable(amex, "2026-12-31"), true);
assert.equal(isChargeable(amex, "2027-01-01"), false);
assert.equal(processingFeeCents(visa, 10000), 320);
assert.equal(processingFeeCents(visa, 1234), 66);
assert.equal(processingFeeCents(amex, 1_000_000), 29030);
assert.equal(receiptLine(visa, 1234), "Charged $12.34 to Visa ending 4242");

assert.equal(describePayment(bank), "First Federal account ending 6789");
assert.equal(describePayment(coop), "Harbor Credit Union account ending 0420");
assert.equal(isChargeable(bank, "2026-01-01"), true);
assert.equal(isChargeable(coop, "2099-12-31"), true);
assert.equal(processingFeeCents(bank, 10000), 80);
assert.equal(processingFeeCents(bank, 1234), 10); // 9.872
assert.equal(processingFeeCents(bank, 62500), 500);
assert.equal(processingFeeCents(coop, 1_000_000), 500);
assert.equal(processingFeeCents(coop, 0), 0);
assert.equal(receiptLine(bank, 1234), "Charged $12.34 to First Federal account ending 6789");
assert.equal(receiptLine(coop, 50000), "Charged $500.00 to Harbor Credit Union account ending 0420");
