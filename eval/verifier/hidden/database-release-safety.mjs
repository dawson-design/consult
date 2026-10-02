import { readdirSync, readFileSync } from "node:fs";

const read = (p) => readFileSync(p, "utf8");
const repoFiles = readdirSync(".", { recursive: true, encoding: "utf8" }).filter((p) => !/(^|\/)(node_modules|\.git)(\/|$)/.test(p));
// "Include rollback and operator notes" names no path: *.rollback.sql, *.down.sql, and a rollback/ directory all count.
const isRollback = (p) => /(^|\/)rollbacks?\//i.test(p) || /rollback[^/]*\.sql$|[._-]down\.sql$/i.test(p);
const forwardFiles = repoFiles.filter((p) => p.startsWith("migrations/") && p.endsWith(".sql") && !isRollback(p)).sort();
const rollbackFiles = repoFiles.filter((p) => p.endsWith(".sql") && isRollback(p)).sort();
// "operator notes" names no file, so any Markdown file in the repository counts.
const operations = repoFiles.filter((p) => p.endsWith(".md")).map(read).join("\n");

// Comments and psql meta-commands go; string and dollar-quoted bodies (DO blocks) become '' so their text cannot pass for SQL.
const SQL_TOKEN = /^[ \t]*\\[^\n]*|--[^\n]*|\/\*[\s\S]*?\*\/|'(?:[^']|'')*'|\$([A-Za-z_]\w*)?\$[\s\S]*?\$\1\$/gm;
const scrub = (sql) => sql.replace(SQL_TOKEN, (token) => (/^\s*(--|\/\*|\\)/.test(token) ? " " : "''"));
const splitStatements = (sql) => scrub(sql).split(";").map((s) => s.replace(/\s+/g, " ").trim()).filter(Boolean);

function fileStatements(path) {
  let inTransaction = false;
  return splitStatements(read(path)).map((sql) => {
    if (/^(begin|start transaction)\b/i.test(sql)) inTransaction = true;
    if (/^(commit|end|rollback|abort)\b/i.test(sql)) inTransaction = false;
    return { sql, inTransaction };
  });
}

const forward = forwardFiles.flatMap(fileStatements);
const rollback = rollbackFiles.flatMap(fileStatements);
const tableName = (name) => name.toLowerCase().replace(/"/g, "").replace(/^public\./, "");
const createdTables = new Set(forward.flatMap(({ sql }) => sql.match(/^create table (?:if not exists )?([\w."]+)/i)?.slice(1).map(tableName) ?? []));
const indexDefinitions = new Map(forward.flatMap(({ sql }) => {
  const name = sql.match(/^create (?:unique )?index (?:concurrently )?(?:if not exists )?([\w"]+) on /i)?.[1];
  return name ? [[tableName(name), sql]] : [];
}));

const plainIndexTable = (sql) => sql.match(/^create (?:unique )?index (?!concurrently\b).*?\bon (?:only )?([\w."]+)/i)?.[1];
const hasValidatedCheck = forward.some(({ sql }) => /\bvalidate constraint\b/i.test(sql));
// One ALTER TABLE can hold several comma-separated actions. A comma inside a type such as numeric(10,2) splits none.
const alterActions = (sql) => sql.split(/,(?=\s*(?:add|alter|drop|validate)\b)/i);
const addsNotNullColumnWithoutDefault = (action) =>
  /\badd column\b/i.test(action) && /(?<!\bis )\bnot null\b/i.test(action) && !/\bdefault\b/i.test(action);
const addsConstraintValidatedUnderLock = (action) =>
  /\badd (?:constraint [\w"]+ )?(?:check|foreign key)\b/i.test(action) && !/\bnot valid\b/i.test(action);
const WRITE_COMPATIBLE_LOCK = /\bin (?:access share|row share|row exclusive|share update exclusive) mode\b/i;

// "suitable for a large live PostgreSQL table" and "Normal writes must continue during rollout": each form
// scans or builds under a lock that blocks writes, or fails outright on a populated table.
const UNSAFE_FORMS = [
  ["non-concurrent index build on an existing table", (sql) => plainIndexTable(sql) !== undefined && !createdTables.has(tableName(plainIndexTable(sql)))],
  ["UNIQUE or PRIMARY KEY constraint that builds its own index", (sql) =>
    /\badd (?:constraint [\w"]+ )?(?:unique|primary key)\b(?! using index)/i.test(sql) || /\badd column\b[^,]*\b(?:unique|primary key)\b/i.test(sql)],
  ["SET NOT NULL without a validated check constraint", (sql) => /\bset not null\b/i.test(sql) && !hasValidatedCheck],
  ["NOT NULL column added without a default", (sql) => alterActions(sql).some(addsNotNullColumnWithoutDefault)],
  ["CHECK or FOREIGN KEY constraint added without NOT VALID", (sql) => alterActions(sql).some(addsConstraintValidatedUnderLock)],
  ["column type change", (sql) => /\balter (?:column )?[\w"]+ (?:set data )?type\b/i.test(sql)],
  ["LOCK TABLE in a mode that blocks writes", (sql) => /^lock\b/i.test(sql) && !WRITE_COMPATIBLE_LOCK.test(sql)],
  ["non-concurrent REINDEX", (sql) => /^reindex\b/i.test(sql) && !/\bconcurrently\b/i.test(sql)],
];
// "must be valid PostgreSQL": CONCURRENTLY cannot run inside a transaction block.
const concurrentInTransaction = ({ sql, inTransaction }) => inTransaction && /\bconcurrently\b/i.test(sql);
// "must be valid PostgreSQL": ADD CONSTRAINT ... USING INDEX rejects partial and expression indexes.
const unusableForConstraint = (definition) => /\bwhere\b/i.test(definition) || /\bon (?:only )?[\w."]+\s*(?:using \w+\s*)?\([^()]*\(/i.test(definition);
const brokenAttachment = forward
  .map(({ sql }) => sql.match(/\badd constraint [\w"]+ (?:unique|primary key) using index ([\w"]+)/i)?.[1])
  .find((name) => name && unusableForConstraint(indexDefinitions.get(tableName(name)) ?? ""));
const rollbackSql = rollback.map(({ sql }) => sql).join("\n");

const checks = [
  ...UNSAFE_FORMS.map(([form, unsafe]) => [`no ${form}`, !forward.some(({ sql }) => unsafe(sql))]),
  ["uses a concurrent unique index build", forward.some(({ sql }) => /^create unique index concurrently\b/i.test(sql))],
  ["does not run CONCURRENTLY inside a transaction block", ![...forward, ...rollback].some(concurrentInTransaction)],
  ["adds a rollback file", rollbackSql.length > 0],
  ["rollback reverses schema or index changes", /\b(drop\s+index|drop\s+constraint|drop\s+column)\b/i.test(rollbackSql)],
  ["documents rollout", /\b(rollout|deploy|apply)\b/i.test(operations)],
  ["documents validation", /\b(validat|verif|check|confirm)\w*/i.test(operations)],
  ["documents rollback", /\brollback\b/i.test(operations)],
  [`does not back a unique constraint with a partial or expression index${brokenAttachment ? ` (${brokenAttachment})` : ""}`, brokenAttachment === undefined],
];
const failed = checks.filter(([, ok]) => !ok).map(([label]) => label);
if (failed.length > 0) {
  console.error("customer email migration: failed checks: " + failed.join(", "));
  process.exit(1);
}
