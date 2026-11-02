#!/bin/bash
# Oracle for the build step: a dependency-free node:http shortener with a
# contract, the scaffold baseline, and tests. Only typescript and @types/node
# are installed, for the typecheck script.
set -euo pipefail
cd /app
mkdir -p src test
cat > package.json <<'JSON'
{
  "name": "links",
  "version": "0.1.0",
  "private": true,
  "type": "module",
  "engines": { "node": ">=22" },
  "scripts": {
    "start": "node src/main.js",
    "test": "node --test",
    "lint": "node --check src/main.js && node --check src/server.js && node --check src/links.js",
    "typecheck": "tsc --noEmit"
  }
}
JSON
npm install --save-dev --no-audit --no-fund typescript@5 @types/node@22 > /dev/null
cat > tsconfig.json <<'JSON'
{ "compilerOptions": { "allowJs": true, "checkJs": true, "noEmit": true, "module": "nodenext", "target": "es2022", "strict": false, "types": ["node"] }, "include": ["src"] }
JSON
printf 'node_modules/\n.env\n' > .gitignore
printf 'PORT=3000\n' > .env.example
cat > openapi.yaml <<'YAML'
openapi: 3.1.0
info: { title: links, version: 0.1.0 }
paths:
  /links:
    post:
      requestBody:
        content:
          application/json: { schema: { type: object, required: [url], properties: { url: { type: string } } } }
          application/x-www-form-urlencoded: { schema: { type: object, required: [url], properties: { url: { type: string } } } }
      responses:
        "201": { description: Created; JSON {slug, shortUrl} or an HTML fragment }
        "400": { description: "JSON {error}: the body is not valid JSON, or the URL is not an absolute http(s) URL" }
  /{slug}:
    get:
      responses:
        "302": { description: Redirect to the stored URL; counts a click }
        "404": { description: Unknown slug }
  /stats:
    get:
      responses:
        "200": { description: "JSON list of {slug, url, clicks}" }
YAML
cat > src/links.js <<'JS'
import { randomBytes } from "node:crypto";

const ABSOLUTE_HTTP = /^https?:\/\/[^\s/\\?#]+[^\s\\]*$/i;

/** @returns {string | null} the normalized URL, or null when it is not an absolute http(s) URL */
export function parseTarget(input) {
  if (typeof input !== "string" || !ABSOLUTE_HTTP.test(input.trim())) return null;
  const url = new URL(input.trim());
  return url.protocol === "http:" || url.protocol === "https:" ? url.href : null;
}

export function newSlug() {
  return randomBytes(6).toString("base64url");
}

export function createLinks() {
  const bySlug = new Map();
  return {
    add(url) {
      const slug = newSlug();
      bySlug.set(slug, { slug, url, clicks: 0 });
      return slug;
    },
    visit(slug) {
      const link = bySlug.get(slug);
      if (!link) return null;
      link.clicks += 1;
      return link.url;
    },
    all: () => [...bySlug.values()].map((link) => ({ ...link })),
  };
}
JS
cat > src/server.js <<'JS'
import http from "node:http";
import { createLinks, parseTarget } from "./links.js";

const PAGE = `<!doctype html><html lang="en"><head><meta charset="utf-8"><title>Links</title></head>
<body><main><h1>Shorten a link</h1>
<form method="post" action="/links"><label for="url">Long URL</label>
<input id="url" name="url" type="url" required><button type="submit">Shorten</button></form>
<p><a href="/stats">Click counts</a></p></main></body></html>`;

async function readBody(req) {
  let raw = "";
  for await (const chunk of req) raw += chunk;
  const type = req.headers["content-type"] ?? "";
  if (!type.includes("json")) return Object.fromEntries(new URLSearchParams(raw));
  try {
    return JSON.parse(raw || "{}");
  } catch {
    return null;
  }
}

const HTML_ESCAPES = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" };
const escapeHtml = (text) => text.replace(/[&<>"']/g, (c) => HTML_ESCAPES[c]);

function sendError(res, status, message) {
  res.writeHead(status, { "content-type": "application/json" });
  res.end(JSON.stringify({ error: message }));
}

export function createServer(links = createLinks()) {
  return http.createServer(async (req, res) => {
    const { pathname } = new URL(req.url, "http://localhost");
    const wantsJson = (req.headers["content-type"] ?? "").includes("json");
    if (req.method === "GET" && pathname === "/") {
      res.writeHead(200, { "content-type": "text/html; charset=utf-8" });
      return res.end(PAGE);
    }
    if (req.method === "GET" && pathname === "/stats") {
      res.writeHead(200, { "content-type": "application/json" });
      return res.end(JSON.stringify(links.all()));
    }
    if (req.method === "POST" && pathname === "/links") {
      const body = await readBody(req);
      if (body === null) return sendError(res, 400, "request body must be valid JSON");
      const target = parseTarget(body.url);
      if (!target) return sendError(res, 400, "url must be an absolute http or https URL");
      const slug = links.add(target);
      const shortUrl = `http://${req.headers.host}/${slug}`;
      res.writeHead(201, { "content-type": wantsJson ? "application/json" : "text/html; charset=utf-8" });
      return res.end(wantsJson ? JSON.stringify({ slug, shortUrl }) : `<p><a href="/${slug}">${escapeHtml(shortUrl)}</a></p>`);
    }
    const target = req.method === "GET" ? links.visit(pathname.slice(1)) : null;
    if (target) {
      res.writeHead(302, { location: target });
      return res.end();
    }
    res.writeHead(404, { "content-type": "text/plain" });
    res.end("not found");
  });
}
JS
cat > src/main.js <<'JS'
import { createServer } from "./server.js";

const port = Number(process.env.PORT ?? 3000);
createServer().listen(port, () => console.log(`links on ${port}`));
JS
cat > test/links.test.js <<'JS'
import test from "node:test";
import assert from "node:assert/strict";
import http from "node:http";
import { createServer } from "../src/server.js";

async function withServer(fn) {
  const server = createServer().listen(0);
  await new Promise((resolve) => server.once("listening", resolve));
  try {
    await fn(`http://127.0.0.1:${server.address().port}`);
  } finally {
    server.close();
  }
}

const shorten = (base, url) =>
  fetch(`${base}/links`, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ url }) });

test("a short link redirects and counts clicks", () =>
  withServer(async (base) => {
    const { slug } = await (await shorten(base, "https://example.com/a")).json();
    const visit = await fetch(`${base}/${slug}`, { redirect: "manual" });
    assert.equal(visit.status, 302);
    assert.equal(visit.headers.get("location"), "https://example.com/a");
    const stats = await (await fetch(`${base}/stats`)).json();
    assert.equal(stats[0].clicks, 1);
  }));

test("refuses targets that are not absolute http(s) URLs", () =>
  withServer(async (base) => {
    for (const bad of ["javascript:alert(1)", "data:text/html,x", "//evil.example", "https:evil.example"]) {
      assert.equal((await shorten(base, bad)).status, 400, bad);
    }
  }));

test("says why when the body is not valid JSON", () =>
  withServer(async (base) => {
    const response = await fetch(`${base}/links`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: "{not json",
    });
    assert.equal(response.status, 400);
    assert.deepEqual(await response.json(), { error: "request body must be valid JSON" });
  }));

test("escapes the short link it writes into the page", () =>
  withServer(async (base) => {
    // fetch drops a custom Host header, so send the request with node:http.
    const { port } = new URL(base);
    const html = await new Promise((resolve, reject) => {
      const request = http.request(
        {
          host: "127.0.0.1",
          port,
          path: "/links",
          method: "POST",
          headers: { host: 'x"><script>', "content-type": "application/x-www-form-urlencoded" },
        },
        (response) => {
          let text = "";
          response.on("data", (chunk) => (text += chunk));
          response.on("end", () => resolve(text));
        },
      );
      request.on("error", reject);
      request.end("url=https%3A%2F%2Fexample.com%2Fa");
    });
    assert.ok(html.includes("x&quot;&gt;&lt;script&gt;"), html);
    assert.ok(!html.includes("<script>"), html);
  }));
JS
cat > README.md <<'MD'
# links

A small self-hosted link shortener for the team: paste a long URL on the page,
get a short link, and see click counts at `/stats`. The HTTP contract is
`openapi.yaml`.

## Install

    npm install

## Run

    PORT=3000 npm start

## Test

    npm test && npm run lint && npm run typecheck
MD
