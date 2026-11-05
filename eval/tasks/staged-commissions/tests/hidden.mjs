// Hidden acceptance check for staged-commissions: every stage's behavior on the
// final tree, so a later stage that breaks an earlier one fails here. Runs in
// the workspace with `node --input-type=module -e`, starts the app with
// `npm start` and a fake FX provider, prints {"s1": 0|1, ...} as its last line,
// and exits non-zero when any stage fails. Money may be integer minor units,
// a major-unit number or decimal string, or an object holding one of those.
import { spawn } from "node:child_process";
import { mkdtempSync } from "node:fs";
import { createServer } from "node:http";
import net from "node:net";
import { tmpdir } from "node:os";
import path from "node:path";

const OAK = 45000;
const STOOL = 8500;

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

// Expected amounts are whole minor units; compare with a tolerance so float noise never fails a correct answer.
function isMoney(value, minor) {
  if (typeof value === "number") return Math.abs(value - minor) < 1e-6 || Math.abs(value - minor / 100) < 1e-6;
  if (typeof value === "string" && value.trim() !== "") {
    const n = Number(value);
    return Number.isFinite(n) && (Math.abs(n - minor) < 1e-6 || Math.abs(n - minor / 100) < 1e-6);
  }
  if (value && typeof value === "object") return Object.entries(value).some(([k, v]) => k !== "currency" && isMoney(v, minor));
  return false;
}

function check(condition, message) {
  if (!condition) throw new Error(message);
}

const is2xx = (r) => r.status >= 200 && r.status < 300;
const is4xx = (r) => r.status >= 400 && r.status < 500;
let emails = 0;

/** A logged-in patron's token, or null when the app has no accounts (stage 3 unbuilt). */
async function patron(base) {
  const email = `p${(emails += 1)}-${Date.now()}@example.com`;
  const signup = await call(base, "POST", "/patrons", { email, password: "correct horse battery" });
  if (!is2xx(signup)) return null;
  const login = await call(base, "POST", "/sessions", { email, password: "correct horse battery" });
  return login.data?.token ?? null;
}

async function place(base, token, pieces = [{ design: "oak-bench", quantity: 1 }]) {
  const placed = await call(base, "POST", "/commissions", { pieces }, token);
  check(placed.status === 201, `placing answered ${placed.status}: ${placed.text.slice(0, 200)}`);
  check(placed.data?.id !== undefined, "placed commission has no id");
  return placed.data;
}

async function stageOne(base) {
  const token = await patron(base);
  const c = await place(base, token, [{ design: "oak-bench", quantity: 1 }, { design: "ash-stool", quantity: 2 }]);
  check(isMoney(c.total, OAK + 2 * STOOL), `total ${JSON.stringify(c.total)} is not 620.00`);
  const shown = await call(base, "GET", `/commissions/${c.id}`, undefined, token);
  check(shown.status === 200 && String(shown.data?.id) === String(c.id), `showing answered ${shown.status}`);
  const early = await call(base, "POST", `/commissions/${c.id}/dispatch`, { consignment: "HJ-EARLY" });
  check(is4xx(early), `dispatch before start answered ${early.status}`);
  const statuses = [JSON.stringify(shown.data.status)];
  for (const [step, body] of [["start"], ["dispatch", { consignment: "HJ-482913" }], ["deliver"]]) {
    const moved = await call(base, "POST", `/commissions/${c.id}/${step}`, body);
    check(is2xx(moved), `${step} answered ${moved.status}`);
    const after = await call(base, "GET", `/commissions/${c.id}`, undefined, token);
    statuses.push(JSON.stringify(after.data?.status));
    if (step === "dispatch") check(after.text.includes("HJ-482913"), "dispatched commission does not show its consignment");
  }
  check(new Set(statuses).size === 4, `statuses do not change at each step: ${statuses.join(", ")}`);
  const unknown = await call(base, "POST", "/commissions", { pieces: [{ design: "teak-throne", quantity: 1 }] }, token);
  check(is4xx(unknown), `unknown design answered ${unknown.status}`);
  const missing = await call(base, "GET", "/commissions/does-not-exist", undefined, token);
  check(missing.status === 404, `missing commission answered ${missing.status}`);
}

async function withdraw(base, token, id, reason) {
  return call(base, "POST", `/commissions/${id}/withdrawal`, reason ? { reason } : {}, token);
}

async function stageTwo(base) {
  const token = await patron(base);
  const free = await place(base, token);
  check(is2xx(await withdraw(base, token, free.id, "changed my mind")), "withdrawal before start failed");
  const freeShown = await call(base, "GET", `/commissions/${free.id}`, undefined, token);
  check(freeShown.text.includes("changed my mind"), "withdrawn commission does not show its reason");
  check(isMoney(freeShown.data?.restockingFee, 0), `fee before start is ${JSON.stringify(freeShown.data?.restockingFee)}`);
  const started = await place(base, token);
  await call(base, "POST", `/commissions/${started.id}/start`);
  check(is2xx(await withdraw(base, token, started.id)), "withdrawal after start failed");
  const startedShown = await call(base, "GET", `/commissions/${started.id}`, undefined, token);
  check(isMoney(startedShown.data?.restockingFee, OAK / 5), `fee after start is ${JSON.stringify(startedShown.data?.restockingFee)}`);
  const sent = await place(base, token);
  await call(base, "POST", `/commissions/${sent.id}/start`);
  await call(base, "POST", `/commissions/${sent.id}/dispatch`, { consignment: "HJ-1" });
  const late = await withdraw(base, token, sent.id);
  check(is4xx(late), `withdrawal after dispatch answered ${late.status}`);
}

async function stageThree(base) {
  const email = `owner-${Date.now()}@example.com`;
  const signup = await call(base, "POST", "/patrons", { email, password: "correct horse battery" });
  check(signup.status === 201, `sign-up answered ${signup.status}`);
  const again = await call(base, "POST", "/patrons", { email, password: "another password 1" });
  check(is4xx(again), `duplicate sign-up answered ${again.status}`);
  const wrong = await call(base, "POST", "/sessions", { email, password: "wrong password" });
  check(is4xx(wrong), `wrong password answered ${wrong.status}`);
  const owner = (await call(base, "POST", "/sessions", { email, password: "correct horse battery" })).data?.token;
  check(owner, "log-in returned no token");
  const other = await patron(base);
  const c = await place(base, owner);
  const anonymous = await call(base, "POST", "/commissions", { pieces: [{ design: "oak-bench", quantity: 1 }] });
  check(is4xx(anonymous), `placing without a token answered ${anonymous.status}`);
  const peek = await call(base, "GET", `/commissions/${c.id}`, undefined, other);
  check(peek.status === 403 || peek.status === 404, `another patron reading answered ${peek.status}`);
  const theirs = await call(base, "GET", "/commissions", undefined, other);
  check(is2xx(theirs) && !theirs.text.includes(`"${c.id}"`), "another patron's list shows the commission");
  const mine = await call(base, "GET", "/commissions", undefined, owner);
  check(is2xx(mine) && mine.text.includes(String(c.id)), "the owner's list misses the commission");
  const steal = await withdraw(base, other, c.id);
  check(steal.status === 403 || steal.status === 404, `another patron withdrawing answered ${steal.status}`);
}

async function stageFour(base) {
  const token = await patron(base);
  const c = await place(base, token);
  const eur = await call(base, "GET", `/commissions/${c.id}?currency=EUR`, undefined, token);
  check(eur.status === 200, `EUR answered ${eur.status}: ${eur.text.slice(0, 200)}`);
  check(isMoney(eur.data?.total, (OAK * 6) / 5) && eur.text.includes("EUR"), `EUR total is ${JSON.stringify(eur.data?.total)}`);
  const gbp = await call(base, "GET", `/commissions/${c.id}`, undefined, token);
  check(isMoney(gbp.data?.total, OAK), `default total is ${JSON.stringify(gbp.data?.total)}`);
  const yen = await call(base, "GET", `/commissions/${c.id}?currency=JPY`, undefined, token);
  check(is4xx(yen), `unsupported currency answered ${yen.status}`);
}

async function stageFive(base) {
  const token = await patron(base);
  const c = await place(base, token);
  check(isMoney(c.deposit, (OAK * 3) / 10), `deposit is ${JSON.stringify(c.deposit)}`);
  check(isMoney(c.balanceDue, (OAK * 7) / 10), `balance due is ${JSON.stringify(c.balanceDue)}`);
  await withdraw(base, token, c.id);
  const refunded = await call(base, "GET", `/commissions/${c.id}`, undefined, token);
  check(isMoney(refunded.data?.refund, (OAK * 3) / 10), `refund before start is ${JSON.stringify(refunded.data?.refund)}`);
  const started = await place(base, token);
  await call(base, "POST", `/commissions/${started.id}/start`);
  await withdraw(base, token, started.id);
  const kept = await call(base, "GET", `/commissions/${started.id}`, undefined, token);
  check(isMoney(kept.data?.refund, OAK / 10), `refund after start is ${JSON.stringify(kept.data?.refund)}`);
  const abroad = await place(base, token);
  const eur = await call(base, "GET", `/commissions/${abroad.id}?currency=EUR`, undefined, token);
  check(isMoney(eur.data?.deposit, (OAK * 3 * 6) / 50), `EUR deposit is ${JSON.stringify(eur.data?.deposit)}`);
}

const STAGES = { s1: stageOne, s2: stageTwo, s3: stageThree, s4: stageFour, s5: stageFive };
const results = {};
const rates = await startRates();
for (const [name, run] of Object.entries(STAGES)) {
  let app = null;
  try {
    app = await startApp({ RATES_URL: rates.url });
    await run(app.base);
    results[name] = 1;
  } catch (error) {
    results[name] = 0;
    console.error(`${name}: ${error.message}`);
  } finally {
    app?.stop();
  }
}
rates.stop();
console.log(JSON.stringify(results));
process.exit(Object.values(results).every((v) => v === 1) ? 0 : 1);
