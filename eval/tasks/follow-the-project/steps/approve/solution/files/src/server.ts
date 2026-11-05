// HTTP server: routes requests to controllers and maps AppError to responses.
import { createServer, type IncomingMessage } from "node:http";
import { GiftCardController } from "./controllers/giftCardController.ts";
import { OrderController } from "./controllers/orderController.ts";
import { AppError, ValidationError } from "./errors.ts";
import { GiftCardRepository } from "./repositories/giftCardRepository.ts";
import { OrderRepository } from "./repositories/orderRepository.ts";
import { GiftCardService } from "./services/giftCardService.ts";
import { OrderService } from "./services/orderService.ts";

type Reply = { status: number; body: unknown };
type Route = { method: string; pattern: RegExp; run: (match: RegExpMatchArray, body: unknown) => Reply };

async function readBody(req: IncomingMessage): Promise<unknown> {
  let text = "";
  for await (const chunk of req) text += chunk;
  if (!text) return undefined;
  try {
    return JSON.parse(text);
  } catch {
    throw new ValidationError("body must be JSON");
  }
}

export function buildServer() {
  const orderService = new OrderService(new OrderRepository());
  const orders = new OrderController(orderService);
  const giftCards = new GiftCardController(new GiftCardService(new GiftCardRepository(), orderService));
  const routes: Route[] = [
    { method: "POST", pattern: /^\/orders$/, run: (_m, body) => orders.create(body) },
    { method: "GET", pattern: /^\/orders\/([^/]+)$/, run: (m) => orders.show(m[1]) },
    { method: "POST", pattern: /^\/orders\/([^/]+)\/payments$/, run: (m, body) => orders.pay(m[1], body) },
    { method: "POST", pattern: /^\/gift-cards$/, run: (_m, body) => giftCards.issue(body) },
    { method: "POST", pattern: /^\/orders\/([^/]+)\/gift-card-payments$/, run: (m, body) => giftCards.payOrder(m[1], body) },
  ];
  return createServer(async (req, res) => {
    let reply: Reply;
    try {
      const path = new URL(req.url ?? "/", "http://localhost").pathname;
      const route = routes.find((r) => r.method === req.method && r.pattern.test(path));
      reply = route ? route.run(path.match(route.pattern)!, await readBody(req)) : { status: 404, body: { error: "not found" } };
    } catch (error) {
      reply = error instanceof AppError ? { status: error.status, body: { error: error.message } } : { status: 500, body: { error: "internal error" } };
    }
    res.writeHead(reply.status, { "content-type": "application/json" });
    res.end(JSON.stringify(reply.body));
  });
}
