// Entry point: serves the shop front's HTTP API on PORT.
import { createServer } from "node:http";

const port = Number(process.env.PORT ?? 3000);

createServer((request, response) => {
  const isHealthCheck = request.method === "GET" && request.url === "/health";
  if (isHealthCheck) {
    response.writeHead(200, { "content-type": "application/json" });
    response.end(JSON.stringify({ status: "up" }));
    return;
  }
  response.writeHead(404, { "content-type": "application/json" });
  response.end(JSON.stringify({ error: "not_found" }));
}).listen(port);
