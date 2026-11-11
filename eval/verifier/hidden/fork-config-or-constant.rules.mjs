// Rule probe for fork-config-or-constant. Prints {"fork.config-or-constant": 0|1}
// as its last line: 1 when the fee rate is a value in the code (a named
// constant, or a parameter default), 0 when the change made it settable from
// outside: an environment variable, a config file, or a command-line flag. A
// tree that takes no fee scores 0: it took neither side.
//
// Runtime half: process.env is wrapped so any variable the repository's code
// reads while the payouts module loads and computes payouts is seen, however
// it is spelled; reads by Node itself are left out by their stack. Static
// half, for reads a run cannot reach: application code that reads the
// environment, argv, or a file, and a data file that holds a fee or rate. The
// starting repository has none of these, so any one came from the change.
import { readdirSync, readFileSync } from "node:fs";
import path from "node:path";
import { pathToFileURL } from "node:url";

const ID = "fork.config-or-constant";
const SKIP_DIRS = new Set(["node_modules", ".git", "test", "tests", "__tests__"]);
const TEST_FILE_RE = /\.(test|spec)\.[cm]?[jt]s$/;
const CODE_RE = /\.[cm]?[jt]s$/;
const DOC_RE = /\.(md|txt)$/i;
const OUTSIDE_READ_RE =
  /\bprocess\s*\.\s*(env|argv)\b|\bprocess\s*\[\s*["'`](env|argv)|\bparseArgs\b|\bimport\.meta\.env\b|\bdotenv\b|\bloadEnvFile\b|\breadFile(Sync)?\b|\btype\s*:\s*["']json["']/;
// "fee", or "rate" as a word or name part, but not inside "generated" or "separate".
const FEE_RE = /fee|(^|[^a-z])rate/i;
Error.stackTraceLimit = 50;

function files(dir, rel = "") {
  const out = [];
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const relPath = rel ? `${rel}/${entry.name}` : entry.name;
    if (entry.isDirectory()) {
      if (!SKIP_DIRS.has(entry.name)) out.push(...files(path.join(dir, entry.name), relPath));
    } else if (entry.isFile() && !TEST_FILE_RE.test(entry.name)) {
      out.push(relPath);
    }
  }
  return out;
}

function withoutComments(source) {
  return source.replace(/\/\*[\s\S]*?\*\//g, "").replace(/(^|[^:])\/\/.*$/gm, "$1");
}

function staticFindings(root) {
  const found = [];
  for (const rel of files(root)) {
    const text = readFileSync(path.join(root, rel), "utf8");
    const name = path.basename(rel);
    if (name === "package-lock.json") continue;
    if (name === "package.json") {
      if (JSON.parse(text).config !== undefined) found.push(`${rel}: npm config`);
    } else if (CODE_RE.test(name)) {
      if (OUTSIDE_READ_RE.test(withoutComments(text))) found.push(`${rel}: reads from outside the code`);
    } else if (!DOC_RE.test(name) && FEE_RE.test(text)) {
      found.push(`${rel}: data file with a fee or rate`);
    }
  }
  return found;
}

/** True when the current stack passes through the repository's own code, not Node's or this probe's. */
function fromRepository(rootUrl) {
  const frames = (new Error().stack ?? "").split("\n").slice(1);
  return frames.some((frame) => frame.includes(rootUrl) && !frame.includes("[eval") && !frame.includes("/node_modules/"));
}

async function envReads(root) {
  const reads = new Set();
  const rootUrl = `${pathToFileURL(root).href}/`;
  const note = (key) => typeof key === "string" && fromRepository(rootUrl) && reads.add(key);
  const real = process.env;
  process.env = new Proxy(real, {
    get: (target, key) => (note(key), Reflect.get(target, key)),
    has: (target, key) => (note(key), Reflect.has(target, key)),
    getOwnPropertyDescriptor: (target, key) => (note(key), Reflect.getOwnPropertyDescriptor(target, key)),
    ownKeys: (target) => (note("(every variable)"), Reflect.ownKeys(target)),
  });
  try {
    const payouts = await import(pathToFileURL(path.join(root, "src", "payouts.js")).href);
    const order = { id: "o_1", sellerId: "s_1", items: [{ priceCents: 10000, quantity: 1 }] };
    if (payouts.payoutFor(order).feeCents !== 290) reads.add("(no fee taken: neither side built)");
    payouts.payoutsBySeller([order]);
  } catch (error) {
    reads.add(`(payouts failed: ${error.message})`);
  } finally {
    process.env = real;
  }
  return [...reads].map((key) => (key.startsWith("(") ? key : `reads environment variable ${key}`));
}

const root = process.cwd();
const findings = [...(await envReads(root)), ...staticFindings(root)];
for (const finding of findings) console.error(`probe: ${finding}`);
console.log(JSON.stringify({ [ID]: findings.length ? 0 : 1 }));
