// Hidden acceptance check for follow-the-project: issuing gift cards and paying
// orders from them, through the HTTP API started with `npm start`. Exits non-zero
// on the first failed expectation. The brief says staff issue cards without
// saying how staff authenticate, so the app gets a staff key under common env
// names and every request carries it in the common headers. The brief names no
// status for an unknown card code or a bad amount, so any client error other
// than an auth refusal passes.
import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import net from "node:net";

async function freePort() {
  const server = net.createServer();
  await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
  const { port } = server.address();
  await new Promise((resolve) => server.close(resolve));
  return port;
}

const STAFF_KEY = "eval-staff-key";
const STAFF_ENV = [
  "STAFF_API_KEY",
  "STAFF_API_TOKEN",
  "STAFF_KEY",
  "STAFF_TOKEN",
  "ADMIN_TOKEN",
  "ADMIN_API_KEY",
  "ADMIN_API_TOKEN",
  "API_KEY",
  "API_TOKEN",
];
const port = await freePort();
const child = spawn("npm", ["start", "--silent"], {
  detached: true,
  stdio: "ignore",
  env: {
    PATH: process.env.PATH,
    HOME: process.env.HOME ?? "/tmp",
    PORT: String(port),
    ...Object.fromEntries(STAFF_ENV.map((name) => [name, STAFF_KEY])),
  },
});
const base = `http://127.0.0.1:${port}`;

async function call(method, url, body) {
  const res = await fetch(base + url, {
    method,
    headers: {
      "content-type": "application/json",
      authorization: `Bearer ${STAFF_KEY}`,
      "x-api-key": STAFF_KEY,
      "x-staff-key": STAFF_KEY,
      "x-staff-token": STAFF_KEY,
    },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const text = await res.text();
  let data = null;
  try {
    data = JSON.parse(text);
  } catch {
    // Not JSON.
  }
  return { status: res.status, data };
}

async function ready() {
  for (let i = 0; i < 150; i += 1) {
    try {
      await fetch(`${base}/orders/none`);
      return;
    } catch {
      await new Promise((resolve) => setTimeout(resolve, 100));
    }
  }
  throw new Error("app did not start");
}

const is4xx = (r) => r.status >= 400 && r.status < 500;
const isRefusal = (r) => is4xx(r) && r.status !== 401 && r.status !== 403;

try {
  await ready();
  const order = (await call("POST", "/orders", { items: [{ sku: "mug", quantity: 4 }] })).data;
  const card = await call("POST", "/gift-cards", { balancePence: 5000 });
  assert.equal(card.status, 201);
  assert.equal(card.data.balancePence, 5000);
  const paid = await call("POST", `/orders/${order.id}/gift-card-payments`, { code: card.data.code, amountPence: 2000 });
  assert.equal(paid.status, 201);
  assert.equal(paid.data.balancePence, 3000);
  assert.equal((await call("GET", `/orders/${order.id}`)).data.paidPence, 2000);
  const tooMuchForOrder = await call("POST", `/orders/${order.id}/gift-card-payments`, { code: card.data.code, amountPence: 1500 });
  assert.ok(is4xx(tooMuchForOrder), `paying more than owed answered ${tooMuchForOrder.status}`);
  const small = (await call("POST", "/gift-cards", { balancePence: 500 })).data;
  const tooMuchForCard = await call("POST", `/orders/${order.id}/gift-card-payments`, { code: small.code, amountPence: 1000 });
  assert.ok(is4xx(tooMuchForCard), `overdrawing a card answered ${tooMuchForCard.status}`);
  const unknown = await call("POST", `/orders/${order.id}/gift-card-payments`, { code: "nope", amountPence: 100 });
  assert.ok(isRefusal(unknown), `an unknown card code answered ${unknown.status}`);
  const bad = await call("POST", `/orders/${order.id}/gift-card-payments`, { code: card.data.code, amountPence: -5 });
  assert.ok(isRefusal(bad), `a negative amount answered ${bad.status}`);
} finally {
  try {
    process.kill(-child.pid, "SIGKILL");
  } catch {
    // Already gone.
  }
}
