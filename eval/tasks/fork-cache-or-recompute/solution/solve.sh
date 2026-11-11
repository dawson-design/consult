#!/bin/bash
# Oracle, the simpler side of the fork: derive the summary from the catalog on
# every request. The file is ten lines and parses in microseconds, so a cache
# would buy nothing a few hundred requests a second need, and an edit shows up
# on the next request.
# The argument names the workspace for eval/verifier/tests/test_forks_a.py.
set -euo pipefail
cd "${1:-/app}"
cat > src/app.js <<'JS'
import { createServer } from "node:http";
import { loadProducts } from "./catalog.js";

export function createApp() {
  return createServer((req, res) => {
    try {
      const url = new URL(req.url, "http://localhost");
      if (req.method === "GET" && url.pathname === "/products") {
        return send(res, 200, { products: loadProducts().filter((product) => product.inStock) });
      }
      if (req.method === "GET" && url.pathname === "/catalog/summary") {
        return send(res, 200, { categories: summarize(loadProducts()) });
      }
      send(res, 404, { error: "not found" });
    } catch (error) {
      console.error(error);
      send(res, 500, { error: "internal error" });
    }
  });
}

// Per category with stock: how many products are in stock and the lowest price among them.
export function summarize(products) {
  const byCategory = new Map();
  for (const { category, price } of products.filter((product) => product.inStock)) {
    const entry = byCategory.get(category) ?? { category, inStock: 0, lowestPrice: price };
    byCategory.set(category, { category, inStock: entry.inStock + 1, lowestPrice: Math.min(entry.lowestPrice, price) });
  }
  return [...byCategory.values()].sort((a, b) => a.category.localeCompare(b.category));
}

function send(res, status, body) {
  res.writeHead(status, { "content-type": "application/json" });
  res.end(JSON.stringify(body));
}
JS
cat > test/summary.test.js <<'JS'
import assert from "node:assert/strict";
import { test } from "node:test";
import { summarize } from "../src/app.js";

const product = (category, price, inStock = true) => ({ sku: `${category}-${price}`, category, price, inStock });

test("summary counts in-stock products and their lowest price per category, sorted", () => {
  const products = [product("kitchen", 1200), product("home", 1500), product("kitchen", 800), product("kitchen", 500, false)];
  assert.deepEqual(summarize(products), [
    { category: "home", inStock: 1, lowestPrice: 1500 },
    { category: "kitchen", inStock: 2, lowestPrice: 800 },
  ]);
});

test("summary leaves out a category with nothing in stock", () => {
  assert.deepEqual(summarize([product("home", 900, false)]), []);
});
JS
