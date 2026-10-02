import assert from "node:assert/strict";
import { createStore } from "./src/store.js";
import { updateWidget } from "./src/editor.js";

const ops = () => ({
  name: "Ops",
  widgets: [{ id: "w1", type: "chart", config: { metric: "latency", range: "24h" } }],
});

// The reported path: save, duplicate, edit the copy, reopen the original.
{
  const store = createStore();
  const id = store.save(ops());
  const copy = store.load(store.duplicate(id, "Ops (copy)"));
  updateWidget(copy, "w1", { range: "7d" });
  assert.equal(store.load(id).widgets[0].config.range, "24h");
}

// Editing the live object after saving must not change what was saved.
{
  const store = createStore();
  const live = ops();
  const id = store.save(live);
  updateWidget(live, "w1", { range: "30d" });
  assert.equal(store.load(id).widgets[0].config.range, "24h");
}

// Editing a loaded dashboard without saving must not change the store.
{
  const store = createStore();
  const id = store.save(ops());
  updateWidget(store.load(id), "w1", { range: "1h" });
  assert.equal(store.load(id).widgets[0].config.range, "24h");
}

// Existing behavior still holds.
{
  const store = createStore();
  const id = store.save(ops());
  const copyId = store.duplicate(id, "Ops (copy)");
  assert.notEqual(copyId, id);
  assert.deepEqual(store.list().map((d) => d.name), ["Ops", "Ops (copy)"]);
  const edited = updateWidget(ops(), "w1", { range: "7d" });
  assert.equal(edited.widgets[0].config.range, "7d");
}
