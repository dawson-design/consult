#!/bin/bash
# Oracle: one check per field, each returning an actionable message or null;
# validateSignup collects every message under its field name. Missing or
# wrong-type values become field errors, never exceptions.
set -euo pipefail
cd /app
cat > src/signup.js <<'JS'
const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
const COUNTRY_PATTERN = /^[A-Z]{2}$/;
const MIN_PASSWORD_LENGTH = 8;
const MIN_AGE = 13;
const MAX_AGE = 120;

function emailError(email) {
  if (typeof email === "string" && EMAIL_PATTERN.test(email)) return null;
  return "Enter a valid email address, such as name@example.com.";
}

function passwordError(password) {
  const text = typeof password === "string" ? password : "";
  const missing = [];
  if (text.length < MIN_PASSWORD_LENGTH) missing.push(`at least ${MIN_PASSWORD_LENGTH} characters`);
  if (!/[a-z]/.test(text)) missing.push("a lowercase letter");
  if (!/[A-Z]/.test(text)) missing.push("an uppercase letter");
  if (!/[0-9]/.test(text)) missing.push("a digit");
  return missing.length === 0 ? null : `Password needs ${missing.join(", ")}.`;
}

function ageError(age) {
  if (Number.isInteger(age) && age >= MIN_AGE && age <= MAX_AGE) return null;
  return `Age must be a whole number from ${MIN_AGE} to ${MAX_AGE}.`;
}

function countryError(country) {
  if (typeof country === "string" && COUNTRY_PATTERN.test(country)) return null;
  return "Country must be a two-letter ISO 3166-1 code in capitals, such as US.";
}

const FIELD_CHECKS = { email: emailError, password: passwordError, age: ageError, country: countryError };

export function validateSignup(input) {
  const fields = input ?? {};
  const errors = {};
  for (const [field, check] of Object.entries(FIELD_CHECKS)) {
    const message = check(fields[field]);
    if (message !== null) errors[field] = message;
  }
  return Object.keys(errors).length === 0 ? { ok: true, value: input } : { ok: false, errors };
}
JS
cat > test/signup.test.js <<'JS'
import assert from "node:assert/strict";
import test from "node:test";
import { validateSignup } from "../src/signup.js";

const valid = { email: "ada@example.com", password: "Hunter2pass", age: 30, country: "US" };

function errorsFor(changes) {
  const result = validateSignup({ ...valid, ...changes });
  assert.equal(result.ok, false);
  return result.errors;
}

test("accepts a valid signup payload", () => {
  const result = validateSignup({
    email: "ada@example.com",
    password: "Hunter2pass",
    age: 30,
    country: "US",
  });
  assert.equal(result.ok, true);
});

test("returns the input unchanged as the value on success", () => {
  assert.deepEqual(validateSignup(valid), { ok: true, value: valid });
});

test("rejects malformed email addresses with a message asking for a valid one", () => {
  for (const email of ["", "not-an-email", "a@", "@example.com", "a b@example.com", "a@@example.com"]) {
    assert.deepEqual(errorsFor({ email }), {
      email: "Enter a valid email address, such as name@example.com.",
    });
  }
});

test("names each missing password requirement", () => {
  assert.match(errorsFor({ password: "Abc1def" }).password, /at least 8 characters/);
  assert.match(errorsFor({ password: "ABCDEFG1" }).password, /a lowercase letter/);
  assert.match(errorsFor({ password: "abcdefg1" }).password, /an uppercase letter/);
  assert.match(errorsFor({ password: "Abcdefgh" }).password, /a digit/);
});

test("names only the password requirements that failed", () => {
  assert.equal(errorsFor({ password: "abcdefg1" }).password, "Password needs an uppercase letter.");
});

test("accepts ages 13 and 120 and rejects 12 and 121", () => {
  assert.equal(validateSignup({ ...valid, age: 13 }).ok, true);
  assert.equal(validateSignup({ ...valid, age: 120 }).ok, true);
  for (const age of [12, 121]) {
    assert.deepEqual(errorsFor({ age }), { age: "Age must be a whole number from 13 to 120." });
  }
});

test("rejects an age that is not an integer", () => {
  for (const age of [30.5, "30", null]) {
    assert.match(errorsFor({ age }).age, /whole number from 13 to 120/);
  }
});

test("requires a two-letter uppercase country code", () => {
  for (const country of ["USA", "us", "U", ""]) {
    assert.match(errorsFor({ country }).country, /two-letter .* in capitals/);
  }
});

test("reports missing and wrong-type fields as field errors instead of throwing", () => {
  const result = validateSignup({ email: 42, country: null });
  assert.equal(result.ok, false);
  assert.deepEqual(Object.keys(result.errors).sort(), ["age", "country", "email", "password"]);
});

test("reports every failing field at once", () => {
  const result = validateSignup({ email: "", password: "x", age: 8, country: "" });
  assert.deepEqual(result, {
    ok: false,
    errors: {
      email: "Enter a valid email address, such as name@example.com.",
      password: "Password needs at least 8 characters, an uppercase letter, a digit.",
      age: "Age must be a whole number from 13 to 120.",
      country: "Country must be a two-letter ISO 3166-1 code in capitals, such as US.",
    },
  });
});

test("never repeats the submitted password in its message", () => {
  assert.doesNotMatch(errorsFor({ password: "secretpw" }).password, /secretpw/);
});
JS
