// Hidden acceptance check for the staged-commissions follow-up change
// (eval/followup/staged-commissions/instruction.md): a 10% discount for a
// patron who has had a commission delivered. It first runs the five stage
// checks unchanged (staged-commissions.mjs, copied beside this file as
// stages.mjs; STAGES_CHECK overrides the path), then stage 6 against the
// HTTP API alone, so it holds for any internal design. Runs in the workspace
// with `node --input-type=module -e`, prints {"s1": 0|1, ..., "s6": 0|1} as its
// last line, and exits non-zero when any stage fails.
import { spawn, spawnSync } from "node:child_process";
import { mkdtempSync, readFileSync } from "node:fs";
import { createServer } from "node:http";
import net from "node:net";
import { tmpdir } from "node:os";
import path from "node:path";

const OAK = 45000;

async function freePort() {
  const server = net.createServer();
  await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
  const { port } = server.address();
  await new Promise((resolve) => server.close(resolve));
  return port;
}

async function startApp(env = {}) {
  const port = await freePort();
  const dir = mkdtempSync(path.join(tmpdir(), "commissions-"));
  const child = spawn("npm", ["start", "--silent"], {
    detached: true,
    stdio: ["ignore", "pipe", "pipe"],
    env: { PATH: process.env.PATH, HOME: process.env.HOME ?? dir, PORT: String(port), DATABASE_PATH: path.join(dir, "app.db"), ...env },
  });
  let output = "";
  child.stdout.on("data", (d) => (output += d));
  child.stderr.on("data", (d) => (output += d));
  const base = `http://127.0.0.1:${port}`;
  for (let i = 0; i < 150; i += 1) {
    try {
      await fetch(`${base}/health`);
      return { base, stop: () => stop(child) };
    } catch {
      await new Promise((resolve) => setTimeout(resolve, 100));
    }
  }
  stop(child);
  throw new Error(`app did not start:\n${output.slice(-1500)}`);
}

function stop(child) {
  try {
    process.kill(-child.pid, "SIGKILL");
  } catch {
    // Already gone.
  }
}

async function startRates(rates = { EUR: 1.2, USD: 1.25 }) {
  const server = createServer((req, res) => {
    res.writeHead(200, { "content-type": "application/json" });
    res.end(JSON.stringify({ base: "GBP", rates }));
  });
  await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
  return { url: `http://127.0.0.1:${server.address().port}`, stop: () => server.close() };
}

async function call(base, method, url, body, token) {
  const headers = { "content-type": "application/json" };
  if (token) headers.authorization = `Bearer ${token}`;
  const res = await fetch(base + url, { method, headers, body: body === undefined ? undefined : JSON.stringify(body) });
  const text = await res.text();
  let data = null;
  try {
    data = JSON.parse(text);
  } catch {
    // Not JSON; checks read text instead.
  }
  return { status: res.status, data: unwrap(data), text };
}

function unwrap(data) {
  return data && typeof data === "object" && data.commission && typeof data.commission === "object" ? data.commission : data;
}

// Money as staged-commissions.mjs accepts it: minor units, major units, a decimal string, or an object holding one.
function isMoney(value, minor) {
  if (typeof value === "number") return Math.abs(value - minor) < 1e-6 || Math.abs(value - minor / 100) < 1e-6;
  if (typeof value === "string" && value.trim() !== "") {
    const n = Number(value);
    return Number.isFinite(n) && (Math.abs(n - minor) < 1e-6 || Math.abs(n - minor / 100) < 1e-6);
  }
  if (value && typeof value === "object") return Object.entries(value).some(([k, v]) => k !== "currency" && isMoney(v, minor));
  return false;
}

/** No discount: the field left out, null, or zero. */
const noDiscount = (value) => value === undefined || value === null || isMoney(value, 0);

function check(condition, message) {
  if (!condition) throw new Error(message);
}

const is2xx = (r) => r.status >= 200 && r.status < 300;

async function patron(base, name) {
  const email = `${name}-${Date.now()}@example.com`;
  await call(base, "POST", "/patrons", { email, password: "correct horse battery" });
  const login = await call(base, "POST", "/sessions", { email, password: "correct horse battery" });
  check(login.data?.token, "log-in returned no token");
  return login.data.token;
}

async function place(base, token) {
  const placed = await call(base, "POST", "/commissions", { pieces: [{ design: "oak-bench", quantity: 1 }] }, token);
  check(placed.status === 201, `placing answered ${placed.status}: ${placed.text.slice(0, 200)}`);
  check(placed.data?.id !== undefined, "placed commission has no id");
  return placed.data;
}

async function show(base, token, id, query = "") {
  const shown = await call(base, "GET", `/commissions/${id}${query}`, undefined, token);
  check(shown.status === 200, `showing answered ${shown.status}: ${shown.text.slice(0, 200)}`);
  return shown.data;
}

async function workshop(base, id, step, body) {
  const moved = await call(base, "POST", `/commissions/${id}/${step}`, body);
  check(is2xx(moved), `${step} answered ${moved.status}`);
}

async function stageSix(base) {
  const token = await patron(base, "returning");
  const first = await place(base, token);
  check(isMoney(first.total, OAK) && noDiscount(first.discount), `first commission total ${JSON.stringify(first.total)}, discount ${JSON.stringify(first.discount)}`);
  await workshop(base, first.id, "start");
  await workshop(base, first.id, "dispatch", { consignment: "HJ-600" });
  const meanwhile = await place(base, token);
  check(isMoney(meanwhile.total, OAK), `placed while the first is dispatched, not delivered: total ${JSON.stringify(meanwhile.total)}`);
  await workshop(base, first.id, "deliver");

  const back = await place(base, token);
  check(isMoney(back.total, (OAK * 9) / 10), `returning total is ${JSON.stringify(back.total)}`);
  check(isMoney(back.discount, OAK / 10), `returning discount is ${JSON.stringify(back.discount)}`);
  check(isMoney(back.deposit, (OAK * 27) / 100), `returning deposit is ${JSON.stringify(back.deposit)}`);
  check(isMoney(back.balanceDue, (OAK * 63) / 100), `returning balance due is ${JSON.stringify(back.balanceDue)}`);

  const kept = await show(base, token, meanwhile.id);
  check(isMoney(kept.total, OAK) && noDiscount(kept.discount), `an earlier order changed price after a delivery: total ${JSON.stringify(kept.total)}`);
  check(isMoney(kept.deposit, (OAK * 3) / 10), `an earlier order's deposit changed after a delivery: ${JSON.stringify(kept.deposit)}`);

  const eur = await show(base, token, back.id, "?currency=EUR");
  check(isMoney(eur.total, (OAK * 9 * 6) / 50), `EUR returning total is ${JSON.stringify(eur.total)}`);
  check(isMoney(eur.discount, (OAK * 6) / 50), `EUR returning discount is ${JSON.stringify(eur.discount)}`);
  check(isMoney(eur.deposit, (OAK * 27 * 6) / 500), `EUR returning deposit is ${JSON.stringify(eur.deposit)}`);

  await workshop(base, back.id, "start");
  const withdrawn = await call(base, "POST", `/commissions/${back.id}/withdrawal`, {}, token);
  check(is2xx(withdrawn), `withdrawal answered ${withdrawn.status}`);
  const after = await show(base, token, back.id);
  check(isMoney(after.restockingFee, (OAK * 9) / 50), `restocking fee on a discounted order is ${JSON.stringify(after.restockingFee)}`);
  check(isMoney(after.refund, (OAK * 9) / 100), `refund on a discounted order is ${JSON.stringify(after.refund)}`);

  const stranger = await place(base, await patron(base, "new"));
  check(isMoney(stranger.total, OAK) && noDiscount(stranger.discount), `another patron got the discount: total ${JSON.stringify(stranger.total)}`);
}

function earlierStages() {
  const script = readFileSync(process.env.STAGES_CHECK ?? "/tests/stages.mjs", "utf8");
  const run = spawnSync(process.execPath, ["--input-type=module", "-e", script], { encoding: "utf8" });
  process.stderr.write(run.stderr ?? "");
  const last = (run.stdout ?? "").trim().split("\n").at(-1) ?? "";
  try {
    return JSON.parse(last);
  } catch {
    console.error(`stages 1-5 printed no result: ${String(run.error ?? last).slice(0, 300)}`);
    return { s1: 0, s2: 0, s3: 0, s4: 0, s5: 0 };
  }
}

const results = earlierStages();
const rates = await startRates();
let app = null;
try {
  app = await startApp({ RATES_URL: rates.url });
  await stageSix(app.base);
  results.s6 = 1;
} catch (error) {
  results.s6 = 0;
  console.error(`s6: ${error.message}`);
} finally {
  app?.stop();
  rates.stop();
}
console.log(JSON.stringify(results));
process.exit(Object.values(results).every((v) => v === 1) ? 0 : 1);
