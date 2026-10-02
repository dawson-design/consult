import assert from "node:assert/strict";
import { handleUserLookup } from "./src/users.js";

const text = (value) => (typeof value === "string" && value.trim().length > 0 ? value : undefined);

// "Error responses should have stable machine-readable and human-readable fields." No field names are
// given, so accept flat {code|error, message}, nested {error: {code, message}}, and Problem Details.
function errorFields(body) {
  const nested = body?.error !== null && typeof body?.error === "object" ? body.error : undefined;
  const source = nested ?? body ?? {};
  return {
    code: text(source.code) ?? text(source.error) ?? text(source.type),
    message: text(source.message) ?? text(source.detail) ?? text(source.title),
  };
}

function assertError(response, status, label) {
  assert.equal(response.status, status, `${label}: status`);
  const fields = errorFields(response.body);
  assert.ok(fields.code, `${label}: needs a non-empty machine-readable code`);
  assert.ok(fields.message, `${label}: needs a non-empty human-readable message`);
  return fields;
}

const missing = assertError(handleUserLookup({ query: {} }), 400, "missing id");
const absent = assertError(handleUserLookup({ query: { id: "missing" } }), 404, "unknown user");
assert.notEqual(missing.code, absent.code, "missing input and missing user need different machine-readable codes");

const found = handleUserLookup({ query: { id: "u_1" } });
assert.equal(found.status, 200);
assert.equal(found.body.id, "u_1");
