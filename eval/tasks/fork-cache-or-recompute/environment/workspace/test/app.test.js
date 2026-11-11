import assert from "node:assert/strict";
import { after, before, test } from "node:test";
import { createApp } from "../src/app.js";

let app;
let base;

before(async () => {
  app = createApp();
  await new Promise((resolve) => app.listen(0, "127.0.0.1", resolve));
  base = `http://127.0.0.1:${app.address().port}`;
});

after(() => app.close());

test("lists only products in stock", async () => {
  const response = await fetch(`${base}/products`);
  assert.equal(response.status, 200);
  const { products } = await response.json();
  assert.ok(products.length > 0);
  assert.ok(products.every((product) => product.inStock));
});
