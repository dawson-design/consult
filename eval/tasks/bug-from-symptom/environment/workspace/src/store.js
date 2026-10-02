import { snapshot } from "./snapshot.js";

export function createStore() {
  const saved = new Map();
  let nextId = 1;

  function save(dashboard) {
    const id = dashboard.id ?? `d${nextId++}`;
    saved.set(id, snapshot({ ...dashboard, id }));
    return id;
  }

  function load(id) {
    const stored = saved.get(id);
    if (!stored) throw new Error(`unknown dashboard ${id}`);
    return snapshot(stored);
  }

  function duplicate(id, name) {
    const copy = snapshot(saved.get(id) ?? load(id));
    delete copy.id;
    return save({ ...copy, name });
  }

  function list() {
    return [...saved.values()].map(({ id, name }) => ({ id, name }));
  }

  return { save, load, duplicate, list };
}
