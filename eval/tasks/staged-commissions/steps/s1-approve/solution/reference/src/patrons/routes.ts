// HTTP routes for sign-up and log-in, and the bearer-token check the
// commission routes use to find the calling patron.
import type { IncomingHttpHeaders } from "node:http";
import type { DatabaseSync } from "node:sqlite";
import { z } from "zod";
import { problem, reply, type Route } from "../http/server.ts";
import { logIn, patronForToken, signUp } from "./accounts.ts";

const Credentials = z.object({
  email: z.string().trim().toLowerCase().pipe(z.email()),
  password: z.string().min(8).max(200),
});

/** The patron behind an `Authorization: Bearer` header, or undefined. */
export function bearerPatron(db: DatabaseSync, headers: IncomingHttpHeaders): string | undefined {
  const match = /^Bearer (\S+)$/.exec(headers.authorization ?? "");
  return match ? patronForToken(db, match[1]) : undefined;
}

/** POST /patrons and POST /sessions. */
export function patronRoutes(db: DatabaseSync): Route[] {
  return [
    {
      method: "POST",
      path: "/patrons",
      handle: async ({ body }) => {
        const credentials = Credentials.safeParse(body);
        if (!credentials.success) return problem(400, "invalid_request", "An email and a password of 8+ characters are required.");
        const created = await signUp(db, credentials.data.email, credentials.data.password);
        if (!created.ok) return problem(409, "email_taken", "That email already has an account.");
        return reply(201, { id: created.value, email: credentials.data.email });
      },
    },
    {
      method: "POST",
      path: "/sessions",
      handle: async ({ body }) => {
        const credentials = Credentials.safeParse(body);
        if (!credentials.success) return problem(400, "invalid_request", "An email and a password are required.");
        const session = await logIn(db, credentials.data.email, credentials.data.password);
        if (!session.ok) return problem(401, "bad_credentials", "Email or password is wrong.");
        return reply(201, { token: session.value });
      },
    },
  ];
}
