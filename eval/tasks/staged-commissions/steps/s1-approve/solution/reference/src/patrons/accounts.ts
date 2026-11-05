// Patron accounts and sessions: sign-up with a unique email, log-in with an
// scrypt-hashed password, and bearer tokens stored only as their SHA-256.
import { createHash, randomBytes, randomUUID, scrypt, timingSafeEqual } from "node:crypto";
import type { DatabaseSync } from "node:sqlite";
import { promisify } from "node:util";
import { err, ok, type Result } from "../result.ts";

const derive = promisify(scrypt) as (password: string, salt: Buffer, length: number) => Promise<Buffer>;
const KEY_LENGTH = 64;
const SQLITE_CONSTRAINT_UNIQUE = 2067;

export type EmailTaken = { readonly kind: "email_taken" };
export type BadCredentials = { readonly kind: "bad_credentials" };

async function hashPassword(password: string): Promise<string> {
  const salt = randomBytes(16);
  const key = await derive(password, salt, KEY_LENGTH);
  return ["scrypt", salt.toString("base64"), key.toString("base64")].join("$");
}

async function passwordMatches(password: string, stored: string): Promise<boolean> {
  const [, salt, expected] = stored.split("$");
  const key = await derive(password, Buffer.from(salt, "base64"), KEY_LENGTH);
  return timingSafeEqual(key, Buffer.from(expected, "base64"));
}

function tokenHash(token: string): string {
  return createHash("sha256").update(token).digest("hex");
}

function isUniqueViolation(error: unknown): boolean {
  return (error as { errcode?: number }).errcode === SQLITE_CONSTRAINT_UNIQUE;
}

/** Create a patron; the email's UNIQUE constraint decides whether it is taken. */
export async function signUp(db: DatabaseSync, email: string, password: string): Promise<Result<string, EmailTaken>> {
  const id = randomUUID();
  const passwordHash = await hashPassword(password);
  try {
    db.prepare("INSERT INTO patrons (id, email, password_hash) VALUES (?, ?, ?)").run(id, email, passwordHash);
  } catch (error) {
    if (isUniqueViolation(error)) return err({ kind: "email_taken" });
    throw error;
  }
  return ok(id);
}

/** A new session token for matching credentials. */
export async function logIn(db: DatabaseSync, email: string, password: string): Promise<Result<string, BadCredentials>> {
  const row = db.prepare("SELECT id, password_hash FROM patrons WHERE email = ?").get(email) as
    | { id: string; password_hash: string }
    | undefined;
  if (!row || !(await passwordMatches(password, row.password_hash))) return err({ kind: "bad_credentials" });
  const token = randomBytes(32).toString("base64url");
  db.prepare("INSERT INTO sessions (token_hash, patron_id) VALUES (?, ?)").run(tokenHash(token), row.id);
  return ok(token);
}

/** The patron a bearer token belongs to, or undefined. */
export function patronForToken(db: DatabaseSync, token: string): string | undefined {
  const row = db.prepare("SELECT patron_id FROM sessions WHERE token_hash = ?").get(tokenHash(token)) as
    | { patron_id: string }
    | undefined;
  return row?.patron_id;
}
