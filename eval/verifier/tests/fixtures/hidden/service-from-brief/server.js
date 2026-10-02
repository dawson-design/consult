// Prints short links on BASE_URL, which defaults to localhost rather than 127.0.0.1.
import { createServer } from "node:http";
import { randomBytes } from "node:crypto";

const port = Number(process.env.PORT ?? 3000);
const baseUrl = process.env.BASE_URL ?? `http://localhost:${port}`;
const links = new Map();

async function readUrl(req) {
  let body = "";
  for await (const chunk of req) body += chunk;
  try {
    return JSON.parse(body).url;
  } catch {
    return undefined;
  }
}

async function shorten(req, res) {
  const target = await readUrl(req);
  if (!URL.canParse(target ?? "") || !["http:", "https:"].includes(new URL(target).protocol)) {
    res.writeHead(400, { "content-type": "application/json" }).end(JSON.stringify({ message: "url must be http(s)" }));
    return;
  }
  const slug = randomBytes(4).toString("hex");
  links.set(slug, { target, clicks: 0 });
  res.writeHead(201, { "content-type": "application/json" }).end(JSON.stringify({ shortUrl: `${baseUrl}/${slug}` }));
}

function follow(req, res) {
  const link = links.get(req.url.slice(1));
  if (!link) return res.writeHead(404).end();
  link.clicks += 1;
  res.writeHead(302, { location: link.target }).end();
}

createServer((req, res) => {
  if (req.method === "POST" && req.url === "/shorten") return shorten(req, res);
  if (req.method === "GET" && req.url === "/") return res.writeHead(200, { "content-type": "text/html" }).end("<form></form>");
  return follow(req, res);
}).listen(port);
