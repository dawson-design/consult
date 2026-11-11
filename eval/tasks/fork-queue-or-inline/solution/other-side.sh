#!/bin/bash
# The other side of the fork, for eval/verifier/tests/test_forks_a.py: the
# request enqueues the confirmation and answers 201 at once; an in-process
# worker drains the queue in the background. It passes the hidden check and
# scores 0 on fork.queue-or-inline.
set -euo pipefail
cd "${1:-/app}"
cat > src/emailQueue.js <<'JS'
import { sendEmail } from "./mailer.js";

const pending = [];
let draining = false;

export function enqueueEmail(message) {
  pending.push(message);
  if (!draining) setImmediate(drain);
}

async function drain() {
  draining = true;
  while (pending.length > 0) {
    const message = pending.shift();
    try {
      await sendEmail(message);
    } catch (error) {
      console.error(`confirmation to ${message.to} failed`, error);
    }
  }
  draining = false;
}
JS
cat > src/app.js <<'JS'
import { createServer } from "node:http";
import { enqueueEmail } from "./emailQueue.js";
import { findOrder, placeOrder } from "./orders.js";

export function createApp() {
  return createServer(async (req, res) => {
    try {
      const url = new URL(req.url, "http://localhost");
      if (req.method === "POST" && url.pathname === "/orders") {
        const result = placeOrder(await readJson(req));
        if (result.error) return send(res, 400, { error: result.error });
        enqueueEmail(confirmation(result.order));
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

function confirmation(order) {
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
