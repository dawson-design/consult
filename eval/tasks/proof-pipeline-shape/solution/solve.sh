#!/bin/bash
# Oracle: drop later records whose normalized email was already seen, then
# normalize each kept record. A phone that does not have exactly 10 digits is
# returned as a failure value and becomes an { record, reason } entry in errors.
# Open points it decides (and a final report would flag): an 11-digit number
# starting with 1 is rejected, per the literal "10 digits" rule; and the first
# record for an email wins even when its phone is bad, so a later duplicate is
# dropped rather than promoted to valid.
set -euo pipefail
cd /app
cat > src/pipeline.js <<'JS'
const US_NATIONAL_DIGITS = 10;

function normalizeEmail(email) {
  return email.trim().toLowerCase();
}

function normalizePhone(phone) {
  const digits = phone.replace(/\D/g, "");
  if (digits.length !== US_NATIONAL_DIGITS) {
    return { ok: false, reason: `phone has ${digits.length} digits; a US number needs ${US_NATIONAL_DIGITS}` };
  }
  return { ok: true, phone: `+1${digits}` };
}

function firstPerEmail(records) {
  const seen = new Set();
  return records.filter((record) => {
    const email = normalizeEmail(record.email);
    if (seen.has(email)) return false;
    seen.add(email);
    return true;
  });
}

function normalizeRecord(record) {
  const phone = normalizePhone(record.phone);
  if (!phone.ok) return { ok: false, error: { record, reason: phone.reason } };
  return { ok: true, record: { ...record, email: normalizeEmail(record.email), phone: phone.phone } };
}

export function processCustomers(records) {
  const results = firstPerEmail(records).map(normalizeRecord);
  return {
    valid: results.filter((result) => result.ok).map((result) => result.record),
    errors: results.filter((result) => !result.ok).map((result) => result.error),
  };
}
JS
cat > test/pipeline.test.js <<'JS'
import assert from "node:assert/strict";
import test from "node:test";
import { processCustomers } from "../src/pipeline.js";

test("returns an empty result for empty input", () => {
  const result = processCustomers([]);
  assert.deepEqual(result, { valid: [], errors: [] });
});

test("lowercases and trims email and writes a 10-digit phone in E.164", () => {
  const result = processCustomers([{ name: "Ada", email: "  Ada@Example.COM ", phone: "(555) 123-4567" }]);
  assert.deepEqual(result, {
    valid: [{ name: "Ada", email: "ada@example.com", phone: "+15551234567" }],
    errors: [],
  });
});

test("keeps the first record when normalized emails match", () => {
  const result = processCustomers([
    { name: "Ada", email: "ada@example.com", phone: "5551234567" },
    { name: "Ada Again", email: " ADA@example.com", phone: "5559876543" },
  ]);
  assert.deepEqual(result.valid, [{ name: "Ada", email: "ada@example.com", phone: "+15551234567" }]);
});

test("puts records whose phone cannot be normalized into errors with a reason", () => {
  const noDigits = { name: "Bad", email: "bad@example.com", phone: "abc" };
  const tooShort = { name: "Short", email: "short@example.com", phone: "555-1234" };
  const tooLong = { name: "Long", email: "long@example.com", phone: "1 555 123 4567" };
  const result = processCustomers([noDigits, tooShort, tooLong]);
  assert.deepEqual(result, {
    valid: [],
    errors: [
      { record: noDigits, reason: "phone has 0 digits; a US number needs 10" },
      { record: tooShort, reason: "phone has 7 digits; a US number needs 10" },
      { record: tooLong, reason: "phone has 11 digits; a US number needs 10" },
    ],
  });
});

test("drops a later duplicate even when the first record for that email failed", () => {
  const first = { name: "Bad", email: "dup@example.com", phone: "abc" };
  const result = processCustomers([first, { name: "Good", email: "Dup@example.com", phone: "5551234567" }]);
  assert.deepEqual(result.valid, []);
  assert.deepEqual(result.errors.map((error) => error.record), [first]);
});

test("leaves the input records unchanged", () => {
  const records = [{ name: "Ada", email: " Ada@Example.COM", phone: "555.123.4567" }];
  processCustomers(records);
  assert.deepEqual(records, [{ name: "Ada", email: " Ada@Example.COM", phone: "555.123.4567" }]);
});
JS
