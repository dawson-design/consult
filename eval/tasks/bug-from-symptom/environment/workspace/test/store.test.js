import test from "node:test";
import assert from "node:assert/strict";
import { createStore } from "../src/store.js";

const ops = () => ({
  name: "Ops",
  widgets: [{ id: "w1", type: "chart", config: { metric: "latency", range: "24h" } }],
});

test("saves and loads a dashboard", () => {
  const store = createStore();
  const id = store.save(ops());
  assert.equal(store.load(id).name, "Ops");
  assert.equal(store.load(id).widgets[0].config.range, "24h");
});

test("duplicates under a new name and id", () => {
  const store = createStore();
  const id = store.save(ops());
  const copyId = store.duplicate(id, "Ops (copy)");
  assert.notEqual(copyId, id);
  assert.deepEqual(store.list().map((d) => d.name), ["Ops", "Ops (copy)"]);
});

test("unknown dashboards throw", () => {
  assert.throws(() => createStore().load("nope"), /unknown dashboard/);
});
