#!/bin/bash
# Oracle: copy widget config deeply when snapshotting, and pin the reported path.
set -euo pipefail
cd /app
cat > src/snapshot.js <<'JS'
// Copies a dashboard for storage so later edits to the live object do not
// leak into what was saved. Widget config is nested, so the copy is deep.
export function snapshot(dashboard) {
  return structuredClone(dashboard);
}
JS
cat > test/snapshot.test.js <<'JS'
import test from "node:test";
import assert from "node:assert/strict";
import { createStore } from "../src/store.js";
import { updateWidget } from "../src/editor.js";

test("editing a duplicate leaves the saved original unchanged", () => {
  const store = createStore();
  const id = store.save({ name: "Ops", widgets: [{ id: "w1", config: { range: "24h" } }] });
  const copy = store.load(store.duplicate(id, "Ops (copy)"));
  updateWidget(copy, "w1", { range: "7d" });
  assert.equal(store.load(id).widgets[0].config.range, "24h");
});
JS
