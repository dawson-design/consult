import test from "node:test";
import assert from "node:assert/strict";
import { updateWidget } from "../src/editor.js";

test("updates a widget's settings", () => {
  const dashboard = { widgets: [{ id: "w1", config: { range: "24h" } }] };
  updateWidget(dashboard, "w1", { range: "7d" });
  assert.equal(dashboard.widgets[0].config.range, "7d");
});

test("unknown widgets throw", () => {
  assert.throws(() => updateWidget({ widgets: [] }, "w9", {}), /unknown widget/);
});
