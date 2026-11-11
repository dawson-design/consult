import { createServer } from "node:http";
import { findOrder, placeOrder } from "./orders.js";

export function createApp() {
  return createServer(async (req, res) => {
    try {
      const url = new URL(req.url, "http://localhost");
      if (req.method === "POST" && url.pathname === "/orders") {
        const result = placeOrder(await readJson(req));
        if (result.error) return send(res, 400, { error: result.error });
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
