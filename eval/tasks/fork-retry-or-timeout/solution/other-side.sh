#!/bin/bash
# The other side of the fork, for eval/verifier/tests/test_forks_a.py: a retry
# loop that calls the carrier up to three times on a timeout, network error, or
# 5xx, with jittered exponential backoff, inside the checkout page's 5 seconds.
# It passes the hidden check and scores 0 on fork.retry-or-timeout.
set -euo pipefail
cd "${1:-/app}"
cat > src/app.js <<'JS'
import { createServer } from "node:http";

const MAX_ATTEMPTS = 3;
const ATTEMPT_TIMEOUT_MS = 1200;
const BASE_BACKOFF_MS = 100;

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
    const estimate = await withRetries(() => fetchEstimate(carrierUrl, postcode));
    send(res, 200, { postcode, days: estimate.days });
  } catch (error) {
    if (!(error instanceof CarrierUnavailable)) throw error;
    send(res, 503, { error: "delivery estimate unavailable" });
  }
}

async function withRetries(call) {
  for (let attempt = 1; ; attempt++) {
    try {
      return await call();
    } catch (error) {
      if (!(error instanceof CarrierUnavailable) || attempt >= MAX_ATTEMPTS) throw error;
      const backoff = BASE_BACKOFF_MS * 2 ** (attempt - 1);
      await new Promise((resolve) => setTimeout(resolve, backoff / 2 + Math.random() * (backoff / 2)));
    }
  }
}

async function fetchEstimate(carrierUrl, postcode) {
  const target = `${carrierUrl}/estimates?postcode=${encodeURIComponent(postcode)}`;
  let response;
  let body;
  try {
    response = await fetch(target, { signal: AbortSignal.timeout(ATTEMPT_TIMEOUT_MS) });
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
