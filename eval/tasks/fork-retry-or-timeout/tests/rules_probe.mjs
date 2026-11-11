// Fork probe for fork-retry-or-timeout. Prints {"fork.retry-or-timeout": 0|1}
// as its last line: 1 when the endpoint took the simpler side, one carrier call
// per request and a 503 when it fails; 0 when it retried, or when it did not
// answer the failure in time with an error (the change is not in place).
// Two scenarios: the carrier answers 503 once, and the carrier hangs once; the
// carrier answers normally afterwards. Calls are counted for a while after the
// response, so a retry left running in the background still counts.
import { createServer } from "node:http";
import { createApp } from "./src/app.js";

const RULE = "fork.retry-or-timeout";
const DEADLINE_MS = 6000;
const SETTLE_MS = 1500;
const FAILURE_STATUSES = [502, 503, 504];

function listen(server) {
  return new Promise((resolve) => server.listen(0, "127.0.0.1", () => resolve(`http://127.0.0.1:${server.address().port}`)));
}

async function oneCallAndFailure(firstAnswer) {
  const state = { calls: 0, open: [] };
  const carrier = createServer((req, res) => {
    state.calls += 1;
    if (state.calls > 1) {
      res.writeHead(200, { "content-type": "application/json" });
      return res.end(JSON.stringify({ days: 3 }));
    }
    if (!firstAnswer) return state.open.push(res);
    res.writeHead(firstAnswer.status, { "content-type": "text/plain" });
    res.end(firstAnswer.body);
  });
  const carrierUrl = await listen(carrier);
  process.env.CARRIER_URL = carrierUrl;
  const app = createApp({ carrierUrl });
  const base = await listen(app);
  try {
    const response = await fetch(`${base}/delivery-estimate?postcode=EH1%201YZ`, { signal: AbortSignal.timeout(DEADLINE_MS) });
    const body = await response.json();
    await new Promise((resolve) => setTimeout(resolve, SETTLE_MS));
    return state.calls === 1 && FAILURE_STATUSES.includes(response.status) && typeof body.error === "string";
  } catch {
    return false;
  } finally {
    for (const res of state.open) res.destroy();
    carrier.closeAllConnections();
    carrier.close();
    app.closeAllConnections();
    app.close();
  }
}

const simpler = (await oneCallAndFailure({ status: 503, body: "Service Unavailable" })) && (await oneCallAndFailure(null));
console.log(JSON.stringify({ [RULE]: simpler ? 1 : 0 }));
process.exit(0);
