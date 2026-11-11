#!/bin/bash
# Oracle, the simpler side of the fork: send the confirmation inline, after the
# order is stored and before the 201. One awaited call, no queue or worker; a
# relay failure surfaces as the request's 500 instead of a lost email.
# The argument names the workspace for eval/verifier/tests/test_forks_a.py.
set -euo pipefail
cd "${1:-/app}"
cat > src/app.js <<'JS'
import { createServer } from "node:http";
import { sendEmail } from "./mailer.js";
import { findOrder, placeOrder } from "./orders.js";

export function createApp() {
  return createServer(async (req, res) => {
    try {
      const url = new URL(req.url, "http://localhost");
      if (req.method === "POST" && url.pathname === "/orders") {
        const result = placeOrder(await readJson(req));
        if (result.error) return send(res, 400, { error: result.error });
        await sendEmail(confirmation(result.order));
        return send(res, 201, result.order);
      }
      const match = url.pathname.match(/^\/orders\/([\w-]+)$/);
      if (req.method === "GET" && match) {
        const order = findOrder(match[1]);
        return order ? send(res, 200, order) : send(res, 404, { error: "order not found" });
      }
      send(res, 404, { error: "not found" });
    } catch (error) {
      console.error(error);
      send(res, 500, { error: "internal error" });
    }
  });
}

export function confirmation(order) {
  const lines = order.items.map((item) => `${item.quantity} x ${item.sku}`);
  return {
    to: order.email,
    subject: `Your order ${order.id} is confirmed`,
    text: [...lines, `Total: £${(order.total / 100).toFixed(2)}`].join("\n"),
  };
}

async function readJson(req) {
  let raw = "";
  for await (const chunk of req) raw += chunk;
  try {
    return JSON.parse(raw);
  } catch {
    return {};
  }
}

function send(res, status, body) {
  res.writeHead(status, { "content-type": "application/json" });
  res.end(JSON.stringify(body));
}
JS
cat > test/confirmation.test.js <<'JS'
import assert from "node:assert/strict";
import { after, before, test } from "node:test";
import { createApp } from "../src/app.js";
import { sentEmails } from "../src/mailer.js";

let app;
let base;

before(async () => {
  app = createApp();
  await new Promise((resolve) => app.listen(0, "127.0.0.1", resolve));
  base = `http://127.0.0.1:${app.address().port}`;
});

after(() => app.close());

function post(body) {
  return fetch(`${base}/orders`, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(body) });
}

test("a placed order gets one confirmation with its id, items, and total", async () => {
  const response = await post({ email: "grace@example.com", items: [{ sku: "NTB-01", quantity: 3 }] });
  assert.equal(response.status, 201);
  const order = await response.json();
  const emails = sentEmails.filter((email) => email.to === "grace@example.com");
  assert.equal(emails.length, 1);
  assert.match(emails[0].subject, new RegExp(order.id));
  assert.match(emails[0].text, /3 x NTB-01/);
  assert.match(emails[0].text, /£33\.00/);
});

test("a rejected order gets no confirmation", async () => {
  const response = await post({ email: "linus@example.com", items: [{ sku: "NOPE", quantity: 1 }] });
  assert.equal(response.status, 400);
  assert.equal(sentEmails.filter((email) => email.to === "linus@example.com").length, 0);
});
JS
