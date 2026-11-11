import assert from "node:assert/strict";
import { createServer } from "node:http";
import { after, before, test } from "node:test";
import { createApp } from "../src/app.js";

let carrier;
let app;
let base;

function listen(server) {
  return new Promise((resolve) => server.listen(0, "127.0.0.1", () => resolve(`http://127.0.0.1:${server.address().port}`)));
}

before(async () => {
  carrier = createServer((req, res) => {
    res.writeHead(200, { "content-type": "application/json" });
    res.end(JSON.stringify({ days: 2 }));
  });
  const carrierUrl = await listen(carrier);
  app = createApp({ carrierUrl });
  base = await listen(app);
});

after(() => {
  app.close();
  carrier.close();
});

test("returns the carrier's estimate for a postcode", async () => {
  const response = await fetch(`${base}/delivery-estimate?postcode=SW1A%201AA`);
  assert.equal(response.status, 200);
  assert.deepEqual(await response.json(), { postcode: "SW1A 1AA", days: 2 });
});

test("rejects a request without a postcode", async () => {
  const response = await fetch(`${base}/delivery-estimate`);
  assert.equal(response.status, 400);
  assert.deepEqual(await response.json(), { error: "postcode is required" });
});
