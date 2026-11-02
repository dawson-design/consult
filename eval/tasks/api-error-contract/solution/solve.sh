#!/bin/bash
# Oracle: 400 for a missing id, 404 for an unknown user, both with one
# {code, message} error body; a found user keeps its 200 response unchanged.
set -euo pipefail
cd /app
cat > src/users.js <<'JS'
const users = new Map([["u_1", { id: "u_1", name: "Ada" }]]);

function errorResponse(status, code, message) {
  return { status, body: { code, message } };
}

export function handleUserLookup(request) {
  const id = request.query.id;
  if (typeof id !== "string" || id.trim() === "") {
    return errorResponse(400, "missing_id", "The id query parameter is required.");
  }
  const user = users.get(id);
  if (!user) return errorResponse(404, "user_not_found", "No user has that id.");
  return { status: 200, body: user };
}
JS
cat > test/users.test.js <<'JS'
import assert from "node:assert/strict";
import test from "node:test";
import { handleUserLookup } from "../src/users.js";

test("returns an existing user", () => {
  assert.equal(handleUserLookup({ query: { id: "u_1" } }).status, 200);
});

test("returns the user's record for a known id", () => {
  assert.deepEqual(handleUserLookup({ query: { id: "u_1" } }), { status: 200, body: { id: "u_1", name: "Ada" } });
});

test("rejects a lookup without an id as a 400 with a code and message", () => {
  assert.deepEqual(handleUserLookup({ query: {} }), {
    status: 400,
    body: { code: "missing_id", message: "The id query parameter is required." },
  });
});

test("rejects an empty id the same way", () => {
  assert.equal(handleUserLookup({ query: { id: "  " } }).body.code, "missing_id");
});

test("reports an unknown user as a 404 with a different code", () => {
  assert.deepEqual(handleUserLookup({ query: { id: "u_404" } }), {
    status: 404,
    body: { code: "user_not_found", message: "No user has that id." },
  });
});
JS
