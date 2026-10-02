import assert from "node:assert/strict";
import test from "node:test";
import { describeLink } from "../src/links.js";

test("splits host and path", () => {
  assert.deepEqual(describeLink("https://example.com/docs/start"), { host: "example.com", path: "/docs/start" });
});
