import assert from "node:assert/strict";
import test from "node:test";
import { convert, UnitError } from "../src/index.js";

test("converts miles to kilometres", () => {
  assert.equal(convert(1, "miles", "kilometres"), 1.609344);
});

test("unknown units throw", () => {
  assert.throws(() => convert(1, "cubits", "metres"), UnitError);
});
