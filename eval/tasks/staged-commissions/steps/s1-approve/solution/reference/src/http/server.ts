// The HTTP transport: matches a request to a route, parses its JSON body once,
// and writes the handler's reply. Every response carries an x-request-id, and
// error bodies repeat it so a patron can quote it; internals stay in the log.
import { randomUUID } from "node:crypto";
import { createServer, type IncomingHttpHeaders, type IncomingMessage, type Server, type ServerResponse } from "node:http";

/** A parsed request as handlers see it. */
export type Request = {
  readonly params: Readonly<Record<string, string>>;
  readonly query: URLSearchParams;
  readonly headers: IncomingHttpHeaders;
  readonly body: unknown;
};

/** What a handler answers. */
export type Reply = { readonly status: number; readonly body: unknown };

export type Route = {
  readonly method: string;
  readonly path: string;
  readonly handle: (request: Request) => Reply | Promise<Reply>;
};

const MAX_BODY_BYTES = 64 * 1024;

/** A JSON reply. */
export const reply = (status: number, body: unknown): Reply => ({ status, body });

/** An error reply with a stable code and a message safe to show. */
export const problem = (status: number, error: string, message: string): Reply => reply(status, { error, message });

function matchPath(pattern: string, path: string): Record<string, string> | undefined {
  const want = pattern.split("/");
  const got = path.split("/");
  if (want.length !== got.length) return undefined;
  const params: Record<string, string> = {};
  for (const [i, part] of want.entries()) {
    if (part.startsWith(":")) params[part.slice(1)] = decodeURIComponent(got[i]);
    else if (part !== got[i]) return undefined;
  }
  return params;
}

function findRoute(routes: readonly Route[], method: string, path: string) {
  for (const route of routes) {
    const params = route.method === method ? matchPath(route.path, path) : undefined;
    if (params) return { route, params };
  }
  return undefined;
}

async function readJson(message: IncomingMessage): Promise<{ ok: true; body: unknown } | { ok: false }> {
  const chunks: Buffer[] = [];
  let size = 0;
  for await (const chunk of message) {
    size += chunk.length;
    if (size > MAX_BODY_BYTES) return { ok: false };
    chunks.push(chunk);
  }
  const text = Buffer.concat(chunks).toString("utf8");
  try {
    return { ok: true, body: text ? JSON.parse(text) : undefined };
  } catch {
    return { ok: false };
  }
}

function send(response: ServerResponse, requestId: string, answer: Reply): void {
  const isError = answer.status >= 400;
  const body = isError ? { ...(answer.body as object), requestId } : answer.body;
  response.writeHead(answer.status, { "content-type": "application/json", "x-request-id": requestId });
  response.end(JSON.stringify(body));
}

async function answer(routes: readonly Route[], message: IncomingMessage): Promise<Reply> {
  const url = new URL(message.url ?? "/", "http://localhost");
  if (url.pathname === "/health") return reply(200, { status: "up" });
  const found = findRoute(routes, message.method ?? "GET", url.pathname);
  if (!found) return problem(404, "not_found", "No such resource.");
  const parsed = await readJson(message);
  if (!parsed.ok) return problem(400, "invalid_json", "The request body is not valid JSON.");
  const request = { params: found.params, query: url.searchParams, headers: message.headers, body: parsed.body };
  return found.route.handle(request);
}

/** An HTTP server for the routes; a handler that throws is a bug, logged and answered with a 500. */
export function createApp(routes: readonly Route[]): Server {
  return createServer(async (message, response) => {
    const requestId = randomUUID();
    try {
      send(response, requestId, await answer(routes, message));
    } catch (error) {
      console.error(`request ${requestId} failed`, error);
      send(response, requestId, problem(500, "internal", "Something went wrong on our side."));
    }
  });
}
