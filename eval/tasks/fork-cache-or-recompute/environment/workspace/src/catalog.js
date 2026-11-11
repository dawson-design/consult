import { readFileSync } from "node:fs";

// The merchandising team edits data/catalog.json by hand.
const CATALOG_FILE = new URL("../data/catalog.json", import.meta.url);

export function loadProducts() {
  return JSON.parse(readFileSync(CATALOG_FILE, "utf8")).products;
}
