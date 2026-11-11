import { createServer } from "node:http";
import { loadProducts } from "./catalog.js";

export function createApp() {
  return createServer((req, res) => {
    try {
      const url = new URL(req.url, "http://localhost");
      if (req.method === "GET" && url.pathname === "/products") {
        return send(res, 200, { products: loadProducts().filter((product) => product.inStock) });
      }
      send(res, 404, { error: "not found" });
    } catch (error) {
      console.error(error);
      send(res, 500, { error: "internal error" });
    }
  });
}

function send(res, status, body) {
  res.writeHead(status, { "content-type": "application/json" });
  res.end(JSON.stringify(body));
}
