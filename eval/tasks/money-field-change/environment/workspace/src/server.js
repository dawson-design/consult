import http from "node:http";
import { createOrder, getOrder, OrderError, toResponse } from "./orders.js";

function send(res, status, body) {
  res.writeHead(status, { "content-type": "application/json" });
  res.end(JSON.stringify(body));
}

async function readJson(req) {
  let raw = "";
  for await (const chunk of req) raw += chunk;
  try {
    return JSON.parse(raw || "{}");
  } catch {
    throw new OrderError(400, "invalid_json", "request body must be JSON");
  }
}

async function route(req) {
  const url = new URL(req.url, "http://localhost");
  if (req.method === "POST" && url.pathname === "/orders") {
    return [201, toResponse(createOrder(await readJson(req)))];
  }
  const match = url.pathname.match(/^\/orders\/([^/]+)$/);
  if (req.method === "GET" && match) return [200, toResponse(getOrder(match[1]))];
  throw new OrderError(404, "not_found", "no such route");
}

export function createServer() {
  return http.createServer(async (req, res) => {
    try {
      const [status, body] = await route(req);
      send(res, status, body);
    } catch (error) {
      if (error instanceof OrderError) return send(res, error.status, { error: { code: error.code, message: error.message } });
      send(res, 500, { error: { code: "internal", message: "internal error" } });
    }
  });
}
