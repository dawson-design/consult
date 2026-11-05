import type { IncomingMessage, ServerResponse } from "node:http";
import { OrderService } from "../services/orderService.ts";

export async function handleRequest(req: IncomingMessage, res: ServerResponse, service: OrderService) {
  const url = new URL(req.url ?? "/", "http://x");
  if (req.method === "POST") {
    if (url.pathname.endsWith("/withdrawal")) {
      const id = url.pathname.split("/")[2];
      let body = "";
      for await (const chunk of req) body += chunk;
      const data = JSON.parse(body || "{}");
      if (typeof data.reason !== "undefined" && typeof data.reason !== "string") {
        res.writeHead(400); res.end(); return;
      }
      try {
        const order = service.cancelOrder(id, data.reason ?? null);
        res.writeHead(200, { "content-type": "application/json" });
        res.end(JSON.stringify(order));
      } catch (e: any) {
        res.writeHead(e.status ?? 500); res.end(JSON.stringify({ error: e.message, stack: e.stack }));
      }
    }
  }
}
