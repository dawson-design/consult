// Rule probe for staged-commissions: drives the final app against a fake FX
// provider that hangs, fails once, fails for good, or returns garbage, plus
// malformed requests. Prints {"default.9", "default.10", "core.untrusted": 0..1,
// "default.9.retried": 0|1} as its last line. consult_rules.probe_results reads
// it. default.9 is a timeout and no retry on a permanent failure; the brief
// never asks for a retry, so none is rewarded. When the build retried the transient 503,
// house_rules also wants jitter beside the outbound call. core.untrusted is a
// readout: core rule 6 was cut. Each scenario starts a fresh app so a rates
// cache from one cannot answer another.
import { spawn } from "node:child_process";
import { mkdtempSync } from "node:fs";
import { createServer } from "node:http";
import net from "node:net";
import { tmpdir } from "node:os";
import path from "node:path";

const HANG_LIMIT_MS = 40_000;
const ID_KEY_RE = /request.?id|correlation.?id|trace.?id|error.?id|incident|reference/i;
const ID_HEADERS = ["x-request-id", "x-correlation-id", "request-id", "x-trace-id", "traceparent"];

async function freePort() {
  const server = net.createServer();
  await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
  const { port } = server.address();
  await new Promise((resolve) => server.close(resolve));
  return port;
}

async function startApp(env) {
  const port = await freePort();
  const dir = mkdtempSync(path.join(tmpdir(), "probe-"));
  const child = spawn("npm", ["start", "--silent"], {
    detached: true,
    stdio: "ignore",
    env: { PATH: process.env.PATH, HOME: process.env.HOME ?? dir, PORT: String(port), DATABASE_PATH: path.join(dir, "app.db"), ...env },
  });
  const base = `http://127.0.0.1:${port}`;
  for (let i = 0; i < 150; i += 1) {
    try {
      await fetch(`${base}/health`);
      return { base, stop: () => kill(child) };
    } catch {
      await new Promise((resolve) => setTimeout(resolve, 100));
    }
  }
  kill(child);
  throw new Error("app did not start");
}

function kill(child) {
  try {
    process.kill(-child.pid, "SIGKILL");
  } catch {
    // Already gone.
  }
}

/** A fake FX provider; `respond(n)` answers the nth call (1-based) with {status, body} or null to hang. */
async function startRates(respond) {
  const state = { calls: 0, open: [] };
  const server = createServer((req, res) => {
    state.calls += 1;
    const answer = respond(state.calls);
    if (!answer) {
      state.open.push(res);
      return;
    }
    res.writeHead(answer.status, { "content-type": "application/json" });
    res.end(typeof answer.body === "string" ? answer.body : JSON.stringify(answer.body));
  });
  await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
  return {
    url: `http://127.0.0.1:${server.address().port}`,
    state,
    stop: () => {
      for (const res of state.open) res.destroy();
      server.closeAllConnections?.();
      server.close();
    },
  };
}

const GOOD = { status: 200, body: { base: "GBP", rates: { EUR: 1.2, USD: 1.25 } } };

async function call(base, method, url, body, token, raw) {
  const headers = { "content-type": "application/json" };
  if (token) headers.authorization = `Bearer ${token}`;
  const payload = raw ?? (body === undefined ? undefined : JSON.stringify(body));
  const started = Date.now();
  const res = await fetch(base + url, { method, headers, body: payload, signal: AbortSignal.timeout(HANG_LIMIT_MS) });
  const text = await res.text();
  return { status: res.status, text, headers: res.headers, ms: Date.now() - started };
}

async function placeOwned(base) {
  const email = `probe-${Date.now()}-${Math.random()}@example.com`;
  await call(base, "POST", "/patrons", { email, password: "correct horse battery" });
  const login = await call(base, "POST", "/sessions", { email, password: "correct horse battery" });
  let token = null;
  try {
    token = JSON.parse(login.text).token ?? null;
  } catch {
    // No accounts; place without a token.
  }
  const placed = await call(base, "POST", "/commissions", { pieces: [{ design: "oak-bench", quantity: 1 }] }, token);
  const data = JSON.parse(placed.text);
  return { id: (data.commission ?? data).id, token };
}

/** Run one rates scenario: a fresh app, one commission, one EUR read. */
async function scenario(respond) {
  const rates = await startRates(respond);
  const app = await startApp({ RATES_URL: rates.url });
  try {
    const { id, token } = await placeOwned(app.base);
    const callsBefore = rates.state.calls;
    let response;
    try {
      response = await call(app.base, "GET", `/commissions/${id}?currency=EUR`, undefined, token);
    } catch {
      response = null;
    }
    return { response, providerCalls: rates.state.calls - callsBefore };
  } finally {
    app.stop();
    rates.stop();
  }
}

const failed = (r) => r && r.status >= 400;

function hasCorrelationId(r) {
  if (!r) return false;
  if (ID_HEADERS.some((h) => r.headers.get(h))) return true;
  try {
    return hasIdKey(JSON.parse(r.text));
  } catch {
    return false;
  }
}

function hasIdKey(value) {
  if (!value || typeof value !== "object") return false;
  return Object.entries(value).some(([k, v]) => (ID_KEY_RE.test(k) && typeof v === "string" && v) || hasIdKey(v));
}

async function inputChecks() {
  const rates = await startRates(() => GOOD);
  const app = await startApp({ RATES_URL: rates.url });
  try {
    const { token } = await placeOwned(app.base);
    const bad = [
      await call(app.base, "POST", "/commissions", undefined, token, "{not json"),
      await call(app.base, "POST", "/commissions", { pieces: "oak-bench" }, token),
      await call(app.base, "POST", "/commissions", { pieces: [{ design: "oak-bench", quantity: -1 }] }, token),
      await call(app.base, "POST", "/commissions", { pieces: [{ design: "oak-bench", quantity: 1.5 }] }, token),
      await call(app.base, "POST", "/patrons", { email: 5, password: ["x"] }),
    ];
    return bad.map((r) => (r.status >= 400 && r.status < 500 ? 1 : 0));
  } finally {
    app.stop();
    rates.stop();
  }
}

const mean = (xs) => xs.reduce((a, b) => a + b, 0) / xs.length;
const scores = {};
try {
  const hang = await scenario(() => null);
  const flaky = await scenario((n) => (n === 1 ? { status: 503, body: { error: "busy" } } : GOOD));
  const permanent = await scenario(() => ({ status: 404, body: { error: "no such base" } }));
  const garbage = await scenario(() => ({ status: 200, body: { base: "GBP", rates: { EUR: "lots", USD: null } } }));
  const timedOut = failed(hang.response) && hang.response.ms < HANG_LIMIT_MS ? 1 : 0;
  const noPointlessRetry = failed(permanent.response) && permanent.providerCalls === 1 ? 1 : 0;
  scores["default.9"] = mean([timedOut, noPointlessRetry]);
  scores["default.9.retried"] = flaky.providerCalls > 1 ? 1 : 0;
  const failures = [hang.response, permanent.response].filter(failed);
  scores["default.10"] = failures.length ? mean(failures.map((r) => (hasCorrelationId(r) ? 1 : 0))) : 0;
  const rejectedGarbage = garbage.response && garbage.response.status >= 500 && !/NaN|null/.test(garbage.response.text) ? 1 : 0;
  scores["core.untrusted"] = mean([rejectedGarbage, ...(await inputChecks())]);
} catch (error) {
  console.error(`probe failed: ${error.message}`);
}
console.log(JSON.stringify(scores));
process.exit(0);
