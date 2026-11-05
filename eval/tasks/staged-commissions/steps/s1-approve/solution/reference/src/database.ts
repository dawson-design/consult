// Opens the SQLite database and creates the schema. The persistence boundary:
// commissions/store.ts and patrons/store.ts are the only other modules that run SQL.
import { DatabaseSync } from "node:sqlite";

const SCHEMA = `
CREATE TABLE IF NOT EXISTS patrons (
  id TEXT PRIMARY KEY,
  email TEXT NOT NULL UNIQUE,
  password_hash TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS sessions (
  token_hash TEXT PRIMARY KEY,
  patron_id TEXT NOT NULL REFERENCES patrons(id)
);
CREATE TABLE IF NOT EXISTS commissions (
  id TEXT PRIMARY KEY,
  patron_id TEXT REFERENCES patrons(id),
  pieces TEXT NOT NULL,
  total_pence INTEGER NOT NULL,
  status TEXT NOT NULL,
  consignment TEXT,
  reason TEXT,
  restocking_fee_pence INTEGER,
  refund_pence INTEGER
);
CREATE INDEX IF NOT EXISTS commissions_patron ON commissions (patron_id);
`;

/** Open (creating if needed) the database at path, with foreign keys on. */
export function openDatabase(path: string): DatabaseSync {
  const db = new DatabaseSync(path);
  db.exec("PRAGMA foreign_keys = ON; PRAGMA journal_mode = WAL;");
  db.exec(SCHEMA);
  return db;
}
