// Hidden check for fork-retry-or-timeout. Accepts both sides of the fork: a
// carrier that fails once may end in an estimate (a retry) or a 503 (no retry).
// Every answer must come within the checkout page's 5 seconds, plus slack.
import assert from "node:assert/strict";
import { createServer } from "node:http";
import { createApp } from "./src/app.js";

const DEADLINE_MS = 6000;
const FAILURE_STATUSES = [502, 503, 504];

function listen(server) {
  return new Promise((resolve) => server.listen(0, "127.0.0.1", () => resolve(`http://127.0.0.1:${server.address().port}`)));
}

/** A fake carrier; `respond(n)` answers the nth call (1-based) with {status, body}, or null to hang. */
async function startCarrier(respond) {
  const state = { calls: 0, open: [] };
  const server = createServer((req, res) => {
    state.calls += 1;
    const answer = respond(state.calls);
    if (!answer) return state.open.push(res);
    res.writeHead(answer.status, { "content-type": typeof answer.body === "string" ? "text/plain" : "application/json" });
    res.end(typeof answer.body === "string" ? answer.body : JSON.stringify(answer.body));
  });
  const url = await listen(server);
  return { url, state, stop: () => { for (const res of state.open) res.destroy(); server.closeAllConnections(); server.close(); } };
}

const ESTIMATE = { status: 200, body: { days: 3 } };
const UNAVAILABLE = { status: 503, body: "Service Unavailable" };

async function scenario(name, respond, expect) {
  const carrier = await startCarrier(respond);
  process.env.CARRIER_URL = carrier.url;
  const app = createApp({ carrierUrl: carrier.url });
  const base = await listen(app);
  try {
    const started = Date.now();
    const response = await fetch(`${base}/delivery-estimate?postcode=EH1%201YZ`, { signal: AbortSignal.timeout(DEADLINE_MS) })
      .catch((error) => assert.fail(`${name}: no answer within ${DEADLINE_MS} ms (${error.name})`));
    const body = await response.json().catch(() => assert.fail(`${name}: response body is not JSON`));
    expect(response.status, body, Date.now() - started);
  } finally {
    carrier.stop();
    app.closeAllConnections();
    app.close();
  }
}

function assertEstimate(name, status, body) {
  assert.equal(status, 200, `${name}: status`);
  assert.equal(body.days, 3, `${name}: days`);
  assert.equal(body.postcode, "EH1 1YZ", `${name}: postcode`);
}

function assertUnavailable(name, status, body) {
  assert.ok(FAILURE_STATUSES.includes(status), `${name}: status ${status} is not 503`);
  assert.equal(typeof body.error, "string", `${name}: error body`);
  assert.ok(body.error.length > 0, `${name}: error message`);
}

await scenario("carrier up", () => ESTIMATE, (status, body) => assertEstimate("carrier up", status, body));
await scenario("carrier hangs", () => null, (status, body) => assertUnavailable("carrier hangs", status, body));
await scenario("carrier down", () => UNAVAILABLE, (status, body) => assertUnavailable("carrier down", status, body));
await scenario("carrier 503 once", (n) => (n === 1 ? UNAVAILABLE : ESTIMATE), (status, body) =>
  status === 200 ? assertEstimate("carrier 503 once", status, body) : assertUnavailable("carrier 503 once", status, body),
);

const app = createApp({ carrierUrl: "http://127.0.0.1:9" });
const base = await listen(app);
const missing = await fetch(`${base}/delivery-estimate`);
assert.equal(missing.status, 400, "missing postcode: status");
app.close();
process.exit(0);
