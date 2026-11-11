// Rule probe for fork-copy-or-home. Prints {"fork.copy-or-home": 0|1} as its
// last line: 1 when responseDueBy follows the business-day rule's one home, 0
// when the rule was written a second time.
//
// The rule has two parts, the weekend and the holiday list, and the starting
// repository writes each once, in src/delivery.js. For each part the probe finds
// the one source file that still holds it (wherever the change moved it), swaps
// that file's copy for another calendar in a scratch copy of the repository,
// and checks that responseDueBy now gives the deadlines the swapped calendar
// gives. A part held in two files was copied, and scores 0 without a swap; so
// does a part the probe cannot find. A tree whose deadlines are wrong under the
// swapped calendar took neither side, or copied the rule.
import { cpSync, mkdtempSync, readdirSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import { pathToFileURL } from "node:url";

const ID = "fork.copy-or-home";
const SKIP_DIRS = new Set(["node_modules", ".git", "test", "tests", "__tests__"]);
const CODE_RE = /\.[cm]?[jt]s$/;
const TEST_FILE_RE = /\.(test|spec)\.[cm]?[jt]s$/;

const WEEKEND = [0, 6];
const HOLIDAYS = ["2026-01-01", "2026-05-25", "2026-07-03", "2026-09-07", "2026-11-26", "2026-12-25"];
const SWAPS = [
  {
    part: "weekend",
    find: /\[\s*0\s*,\s*6\s*\]|\[\s*6\s*,\s*0\s*\]/,
    replace: "[5, 6]",
    calendar: { weekend: [5, 6], holidays: HOLIDAYS },
  },
  {
    part: "holidays",
    find: /2026-11-26/,
    replace: "2026-11-24",
    calendar: { weekend: WEEKEND, holidays: HOLIDAYS.map((d) => (d === "2026-11-26" ? "2026-11-24" : d)) },
  },
];

function sourceFiles(dir, rel = "") {
  const out = [];
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const relPath = rel ? `${rel}/${entry.name}` : entry.name;
    if (entry.isDirectory()) {
      if (!SKIP_DIRS.has(entry.name)) out.push(...sourceFiles(path.join(dir, entry.name), relPath));
    } else if (entry.isFile() && CODE_RE.test(entry.name) && !TEST_FILE_RE.test(entry.name)) {
      out.push(relPath);
    }
  }
  return out;
}

// The deadline under a given calendar, written from the brief.
function addDay(date) {
  const day = new Date(`${date}T00:00:00Z`);
  day.setUTCDate(day.getUTCDate() + 1);
  return day.toISOString().slice(0, 10);
}

function expectedDue(calendar, ticket, days) {
  const businessDay = (date) =>
    !calendar.weekend.includes(new Date(`${date}T00:00:00Z`).getUTCDay()) && !calendar.holidays.includes(date);
  let due = ticket.openedOn;
  while (!businessDay(due)) due = addDay(due);
  for (let left = days; left > 0; ) {
    due = addDay(due);
    if (businessDay(due)) left -= 1;
  }
  return due;
}

function tickets() {
  const out = [];
  for (const [start, end] of [
    ["2026-03-01", "2026-03-21"],
    ["2026-11-14", "2026-12-05"],
  ]) {
    for (let date = start; date <= end; date = addDay(date)) {
      out.push([{ plan: "business", subject: "Invoice question", openedOn: date }, 1]);
      out.push([{ plan: "free", subject: "Change my email", openedOn: date }, 3]);
    }
  }
  return out;
}

async function followsSwap(root, files, swap) {
  const holders = files.filter((rel) => swap.find.test(readFileSync(path.join(root, rel), "utf8")));
  if (holders.length !== 1) {
    return `${swap.part}: held in ${holders.length} source files (${holders.join(", ") || "none"})`;
  }
  const scratch = mkdtempSync(path.join(tmpdir(), "fork-home-"));
  try {
    cpSync(root, scratch, { recursive: true, filter: (src) => !/[\\/](node_modules|\.git)$/.test(src) });
    const home = path.join(scratch, holders[0]);
    writeFileSync(home, readFileSync(home, "utf8").replace(new RegExp(swap.find.source, "g"), swap.replace));
    const { responseDueBy } = await import(pathToFileURL(path.join(scratch, "src", "tickets.js")).href);
    for (const [ticket, days] of tickets()) {
      const want = expectedDue(swap.calendar, ticket, days);
      const got = responseDueBy(ticket);
      if (got !== want) {
        return `${swap.part}: swapped in ${holders[0]}, but a ${ticket.plan} ticket opened ${ticket.openedOn} is due ${got}, not ${want}`;
      }
    }
    return null;
  } catch (error) {
    return `${swap.part}: ${error.message}`;
  } finally {
    rmSync(scratch, { recursive: true, force: true });
  }
}

const root = process.cwd();
const files = sourceFiles(root);
const findings = [];
for (const swap of SWAPS) {
  const finding = await followsSwap(root, files, swap);
  if (finding) findings.push(finding);
}
for (const finding of findings) console.error(`probe: ${finding}`);
console.log(JSON.stringify({ [ID]: findings.length ? 0 : 1 }));
