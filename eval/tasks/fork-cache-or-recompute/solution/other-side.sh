#!/bin/bash
# The other side of the fork, for eval/verifier/tests/test_forks_a.py: an
# in-memory cache of the summary, invalidated when the catalog file's mtime
# changes. It passes the hidden check and scores 0 on fork.cache-or-recompute.
set -euo pipefail
cd "${1:-/app}"
cat > src/app.js <<'JS'
import { statSync } from "node:fs";
import { createServer } from "node:http";
import { loadProducts } from "./catalog.js";

const CATALOG_FILE = new URL("../data/catalog.json", import.meta.url);
let cached = { mtimeMs: -1, categories: [] };

export function createApp() {
  return createServer((req, res) => {
    try {
      const url = new URL(req.url, "http://localhost");
      if (req.method === "GET" && url.pathname === "/products") {
        return send(res, 200, { products: loadProducts().filter((product) => product.inStock) });
      }
      if (req.method === "GET" && url.pathname === "/catalog/summary") {
        return send(res, 200, { categories: cachedSummary() });
      }
      send(res, 404, { error: "not found" });
    } catch (error) {
      console.error(error);
      send(res, 500, { error: "internal error" });
    }
  });
}

function cachedSummary() {
  const { mtimeMs } = statSync(CATALOG_FILE);
  if (mtimeMs !== cached.mtimeMs) cached = { mtimeMs, categories: summarize(loadProducts()) };
  return cached.categories;
}

function summarize(products) {
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
