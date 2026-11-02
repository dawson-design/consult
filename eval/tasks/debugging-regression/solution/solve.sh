#!/bin/bash
# Oracle: merge plain objects key by key so nested settings survive, replace
# arrays and other values with copies, never write into the inputs, reject a
# patch that is not a JSON object, and skip prototype keys at every level.
set -euo pipefail
cd /app
cat > src/profile.js <<'JS'
// Keys that could reach a prototype when assigned. Skipped at every level,
// because patches are untrusted JSON.
const PROTOTYPE_KEYS = new Set(["__proto__", "constructor", "prototype"]);

function isJsonObject(value) {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function safeEntries(object) {
  return Object.entries(object).filter(([key]) => !PROTOTYPE_KEYS.has(key));
}

function copyValue(value) {
  if (Array.isArray(value)) return value.map(copyValue);
  if (isJsonObject(value)) return mergeObjects({}, value);
  return value;
}

function mergeObjects(base, patch) {
  const result = {};
  for (const [key, value] of safeEntries(base)) result[key] = copyValue(value);
  for (const [key, value] of safeEntries(patch)) {
    const current = Object.hasOwn(result, key) ? result[key] : undefined;
    const bothObjects = isJsonObject(current) && isJsonObject(value);
    result[key] = bothObjects ? mergeObjects(current, value) : copyValue(value);
  }
  return result;
}

export function mergeProfile(existing, patch) {
  if (!isJsonObject(patch)) throw new TypeError("patch must be a JSON object");
  return mergeObjects(existing, patch);
}
JS
cat > test/profile.test.js <<'JS'
import assert from "node:assert/strict";
import test from "node:test";
import { mergeProfile } from "../src/profile.js";

test("updates top-level values", () => {
  assert.deepEqual(mergeProfile({ name: "A" }, { name: "B" }), { name: "B" });
});

test("keeps sibling nested settings when a patch changes one nested value", () => {
  const existing = { id: "u_1", preferences: { theme: "dark", email: true } };
  assert.deepEqual(mergeProfile(existing, { preferences: { email: false } }), {
    id: "u_1",
    preferences: { theme: "dark", email: false },
  });
});

test("replaces arrays and leaves both inputs unchanged", () => {
  const existing = { tags: ["admin"], preferences: { theme: "dark" } };
  const patch = { tags: ["beta"], preferences: { theme: "light" } };
  const merged = mergeProfile(existing, patch);
  assert.deepEqual(merged, { tags: ["beta"], preferences: { theme: "light" } });
  assert.deepEqual(existing, { tags: ["admin"], preferences: { theme: "dark" } });
  assert.deepEqual(patch, { tags: ["beta"], preferences: { theme: "light" } });
  merged.tags.push("changed");
  merged.preferences.theme = "changed";
  assert.deepEqual(patch, { tags: ["beta"], preferences: { theme: "light" } });
});

test("a null patch value replaces the existing value", () => {
  assert.deepEqual(mergeProfile({ bio: "hi" }, { bio: null }), { bio: null });
});

test("rejects a patch that is not a JSON object", () => {
  for (const patch of [null, ["a"], "name", 3]) {
    assert.throws(() => mergeProfile({ name: "A" }, patch), {
      name: "TypeError",
      message: "patch must be a JSON object",
    });
  }
});

function withCleanPrototype(property, run) {
  try {
    run();
  } finally {
    delete Object.prototype[property];
  }
}

test("a parsed __proto__ key at any depth changes no prototype", () => {
  withCleanPrototype("polluted", () => {
    const patch = JSON.parse(
      '{"__proto__":{"polluted":"top"},"preferences":{"__proto__":{"polluted":"nested"}}}',
    );
    const merged = mergeProfile({ preferences: { theme: "dark" } }, patch);
    assert.equal({}.polluted, undefined);
    assert.equal(merged.polluted, undefined);
    assert.equal(merged.preferences.polluted, undefined);
    assert.equal(Object.getPrototypeOf(merged), Object.prototype);
    assert.equal(Object.getPrototypeOf(merged.preferences), Object.prototype);
  });
});

test("a parsed constructor.prototype key changes no prototype", () => {
  withCleanPrototype("ctorPolluted", () => {
    const patch = JSON.parse('{"constructor":{"prototype":{"ctorPolluted":"yes"}}}');
    const merged = mergeProfile({ id: "u_3" }, patch);
    assert.equal({}.ctorPolluted, undefined);
    assert.deepEqual(merged, { id: "u_3" });
  });
});
JS
