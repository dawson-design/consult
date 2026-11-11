// Fork probe for fork-cache-or-recompute. Prints {"fork.cache-or-recompute":
// 0|1} as its last line: 1 when every summary request reads the catalog file
// (the simpler side, derived per request), 0 when fewer reads served the same
// requests (a cache), or when the summary is wrong or missing.
// It counts reads by wrapping node:fs before the app loads, which reaches named
// ESM imports through syncBuiltinESMExports.
import { createRequire, syncBuiltinESMExports } from "node:module";
import { isDeepStrictEqual } from "node:util";

const RULE = "fork.cache-or-recompute";
const REQUESTS = 10;
const require = createRequire(import.meta.url);
const fs = require("node:fs");
let reads = 0;

function counted(owner, name) {
  const original = owner[name];
  owner[name] = function (path, ...rest) {
    if (String(path?.href ?? path).endsWith("catalog.json")) reads += 1;
    return original.call(this, path, ...rest);
  };
}
counted(fs, "readFileSync");
counted(fs, "readFile");
counted(fs, "createReadStream");
counted(fs.promises, "readFile");
syncBuiltinESMExports();

function expectedSummary(products) {
  const byCategory = new Map();
  for (const { category, price } of products.filter((product) => product.inStock)) {
    const entry = byCategory.get(category) ?? { category, inStock: 0, lowestPrice: price };
    byCategory.set(category, { category, inStock: entry.inStock + 1, lowestPrice: Math.min(entry.lowestPrice, price) });
  }
  return [...byCategory.values()].sort((a, b) => (a.category < b.category ? -1 : 1));
}

async function probe() {
  const expected = expectedSummary(JSON.parse(fs.readFileSync("data/catalog.json", "utf8")).products);
  const { createApp } = await import(`${process.cwd()}/src/app.js`);
  const app = createApp();
  await new Promise((resolve) => app.listen(0, "127.0.0.1", resolve));
  const base = `http://127.0.0.1:${app.address().port}`;
  try {
    const summary = async () => {
      const response = await fetch(`${base}/catalog/summary`);
      return response.status === 200 && isDeepStrictEqual((await response.json()).categories, expected);
    };
    if (!(await summary())) return false;
    reads = 0;
    for (let i = 0; i < REQUESTS; i += 1) {
      if (!(await summary())) return false;
    }
    return reads >= REQUESTS;
  } finally {
    app.closeAllConnections();
    app.close();
  }
}

const simpler = await probe().catch(() => false);
console.log(JSON.stringify({ [RULE]: simpler ? 1 : 0 }));
process.exit(0);
