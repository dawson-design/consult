// Hidden check for fork-cache-or-recompute. Accepts both sides of the fork:
// the summary may be derived per request or cached, as long as it is right and
// a hand edit to data/catalog.json shows up within a second. The edit is undone
// before the check exits.
import assert from "node:assert/strict";
import { readFileSync, writeFileSync } from "node:fs";
import { createApp } from "./src/app.js";

const CATALOG = "data/catalog.json";
const SHOW_UP_MS = 1200;
const original = readFileSync(CATALOG, "utf8");

function expectedSummary(products) {
  const byCategory = new Map();
  for (const { category, price } of products.filter((product) => product.inStock)) {
    const entry = byCategory.get(category) ?? { category, inStock: 0, lowestPrice: price };
    byCategory.set(category, { category, inStock: entry.inStock + 1, lowestPrice: Math.min(entry.lowestPrice, price) });
  }
  return [...byCategory.values()].sort((a, b) => (a.category < b.category ? -1 : 1));
}

async function getJson(base, path) {
  const response = await fetch(`${base}${path}`);
  assert.equal(response.status, 200, `${path}: status`);
  return response.json();
}

function edited(products) {
  return [
    ...products.map((product) => {
      if (product.sku === "TWL-01") return { ...product, price: 650 };
      if (product.sku === "PEN-02") return { ...product, inStock: true };
      if (product.sku === "CDL-01") return { ...product, inStock: false };
      return product;
    }),
    { sku: "TRW-01", name: "Hand trowel", category: "garden", price: 1700, inStock: true },
  ];
}

const app = createApp();
await new Promise((resolve) => app.listen(0, "127.0.0.1", resolve));
const base = `http://127.0.0.1:${app.address().port}`;
try {
  const products = JSON.parse(original).products;
  const before = await getJson(base, "/catalog/summary");
  assert.deepEqual(before.categories, expectedSummary(products), "summary of the shipped catalog");
  const listed = await getJson(base, "/products");
  assert.ok(listed.products.every((product) => product.inStock), "/products still lists only products in stock");

  const changed = edited(products);
  writeFileSync(CATALOG, JSON.stringify({ products: changed }, null, 2));
  await new Promise((resolve) => setTimeout(resolve, SHOW_UP_MS));
  const after = await getJson(base, "/catalog/summary");
  assert.deepEqual(after.categories, expectedSummary(changed), "summary after a hand edit");
} finally {
  writeFileSync(CATALOG, original);
  app.closeAllConnections();
  app.close();
}
process.exit(0);
