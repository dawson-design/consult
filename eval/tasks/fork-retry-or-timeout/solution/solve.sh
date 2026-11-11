#!/bin/bash
# Oracle, the simpler side of the fork: one carrier call per request, cut off
# by a timeout under the checkout page's 5 seconds, and any carrier failure
# (timeout, network error, non-2xx, unreadable body) mapped to a 503. No retry.
# The argument names the workspace for eval/verifier/tests/test_forks_a.py.
set -euo pipefail
cd "${1:-/app}"
cat > src/app.js <<'JS'
import { createServer } from "node:http";

// Leaves the checkout page, which gives up after 5 seconds, time to read our answer.
const CARRIER_TIMEOUT_MS = 4000;

class CarrierUnavailable extends Error {}

// The checkout page asks this service how many days delivery to a postcode
// takes. The answer comes from the carrier's estimates API at `carrierUrl`.
export function createApp({ carrierUrl = process.env.CARRIER_URL } = {}) {
  return createServer(async (req, res) => {
    try {
      const url = new URL(req.url, "http://localhost");
      if (req.method === "GET" && url.pathname === "/delivery-estimate") {
        return await deliveryEstimate(url, res, carrierUrl);
      }
      send(res, 404, { error: "not found" });
    } catch (error) {
      console.error(error);
      send(res, 500, { error: "internal error" });
    }
  });
}

async function deliveryEstimate(url, res, carrierUrl) {
  const postcode = url.searchParams.get("postcode")?.trim();
  if (!postcode) return send(res, 400, { error: "postcode is required" });
  try {
    const estimate = await fetchEstimate(carrierUrl, postcode);
    send(res, 200, { postcode, days: estimate.days });
  } catch (error) {
    if (!(error instanceof CarrierUnavailable)) throw error;
    console.warn(`carrier unavailable: ${error.message}`);
    send(res, 503, { error: "delivery estimate unavailable" });
  }
}

async function fetchEstimate(carrierUrl, postcode) {
  const target = `${carrierUrl}/estimates?postcode=${encodeURIComponent(postcode)}`;
  let response;
  let body;
  try {
    response = await fetch(target, { signal: AbortSignal.timeout(CARRIER_TIMEOUT_MS) });
    body = await response.json();
  } catch (error) {
    throw new CarrierUnavailable(error.message, { cause: error });
  }
  if (!response.ok || !Number.isInteger(body?.days)) {
    throw new CarrierUnavailable(`status ${response.status}`);
  }
  return body;
}

function send(res, status, body) {
  res.writeHead(status, { "content-type": "application/json" });
  res.end(JSON.stringify(body));
}
JS
cat > test/app.test.js <<'JS'
import assert from "node:assert/strict";
import { createServer } from "node:http";
import { after, before, test } from "node:test";
import { createApp } from "../src/app.js";

let carrier;
let app;
let base;
let answer = (res) => reply(res, 200, { days: 2 });
const open = [];

function listen(server) {
  return new Promise((resolve) => server.listen(0, "127.0.0.1", () => resolve(`http://127.0.0.1:${server.address().port}`)));
}

function reply(res, status, body) {
  res.writeHead(status, { "content-type": "application/json" });
  res.end(JSON.stringify(body));
}

before(async () => {
  carrier = createServer((req, res) => answer(res));
  const carrierUrl = await listen(carrier);
  app = createApp({ carrierUrl });
  base = await listen(app);
});

after(() => {
  for (const res of open) res.destroy();
  app.close();
  carrier.close();
});

test("returns the carrier's estimate for a postcode", async () => {
  answer = (res) => reply(res, 200, { days: 2 });
  const response = await fetch(`${base}/delivery-estimate?postcode=SW1A%201AA`);
  assert.equal(response.status, 200);
  assert.deepEqual(await response.json(), { postcode: "SW1A 1AA", days: 2 });
});

test("rejects a request without a postcode", async () => {
  const response = await fetch(`${base}/delivery-estimate`);
  assert.equal(response.status, 400);
  assert.deepEqual(await response.json(), { error: "postcode is required" });
});

test("answers 503 when the carrier answers 503", async () => {
  answer = (res) => {
    res.writeHead(503);
    res.end("Service Unavailable");
  };
  const response = await fetch(`${base}/delivery-estimate?postcode=SW1A`);
  assert.equal(response.status, 503);
  assert.deepEqual(await response.json(), { error: "delivery estimate unavailable" });
});

test("answers 503 within 5 seconds when the carrier hangs", async () => {
  answer = (res) => open.push(res);
  const started = Date.now();
  const response = await fetch(`${base}/delivery-estimate?postcode=SW1A`);
  assert.equal(response.status, 503);
  assert.ok(Date.now() - started < 5000);
});
JS
