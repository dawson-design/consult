// Rule probe for fork-special-case-or-reshape. Prints
// {"fork.special-case-or-reshape": 0|1} as its last line: 1 when the code
// tells payment methods apart in at most one function (a lookup or variant
// with one dispatch point), 0 when it does so in two or more (a bank check or
// flag in each function, or a switch on the method in each).
//
// It measures behaviour, not names. With V8's block coverage on, it calls
// every public function once with a card and once with a bank account whose
// shared fields match, and takes the coverage of each run apart. A function
// that runs for both methods but takes a different branch for each is a place
// that tells them apart. Functions that run for one method only, such as each
// entry of a lookup, are that method's own behaviour and do not count, and
// neither do branches that run for neither (a guard for an unknown method).
// A tree whose bank accounts give the wrong answers took neither side, and
// scores 0.
import { Session } from "node:inspector/promises";
import path from "node:path";
import { pathToFileURL } from "node:url";

const ID = "fork.special-case-or-reshape";
const card = { id: "pm_1", method: "card", cardBrand: "Visa", cardLast4: "4242", expMonth: 8, expYear: 2027 };
const bank = { id: "pm_2", method: "bank_transfer", bankName: "First Federal", accountLast4: "6789" };
const TODAY = "2026-11-11";
const AMOUNT = 1234;
const BANK_ANSWERS = {
  describePayment: "First Federal account ending 6789",
  isChargeable: true,
  processingFeeCents: 10,
  receiptLine: "Charged $12.34 to First Federal account ending 6789",
};

function run(payments, payment) {
  return {
    describePayment: payments.describePayment(payment),
    isChargeable: payments.isChargeable(payment, TODAY),
    processingFeeCents: payments.processingFeeCents(payment, AMOUNT),
    receiptLine: payments.receiptLine(payment, AMOUNT),
  };
}

/** Per function executed in a run: key -> {name, url, ranges}. Only the repository's own files. */
function functionsRun(coverage, rootUrl) {
  const out = new Map();
  for (const script of coverage.result) {
    if (!script.url.startsWith(rootUrl) || script.url.includes("/node_modules/")) continue;
    for (const fn of script.functions) {
      const [whole, ...blocks] = fn.ranges;
      if (!whole || whole.count === 0) continue;
      out.set(`${script.url}:${whole.startOffset}`, { name: fn.functionName || "(anonymous)", url: script.url, whole, blocks });
    }
  }
  return out;
}

/** Whether `offset` ran: the count of the innermost range that holds it. */
function ranAt(fn, offset) {
  let best = fn.whole;
  for (const range of fn.blocks) {
    const inside = range.startOffset <= offset && offset < range.endOffset;
    if (inside && range.endOffset - range.startOffset <= best.endOffset - best.startOffset) best = range;
  }
  return best.count > 0;
}

/** Functions that ran for both methods and took a different branch for each. */
function telling(cardRun, bankRun) {
  const places = [];
  for (const [key, a] of cardRun) {
    const b = bankRun.get(key);
    if (!b) continue;
    const offsets = new Set([...a.blocks, ...b.blocks].flatMap((r) => [r.startOffset, r.endOffset]));
    if ([...offsets].some((offset) => ranAt(a, offset) !== ranAt(b, offset))) {
      places.push(`${a.name} (${path.basename(new URL(a.url).pathname)})`);
    }
  }
  return places;
}

const root = process.cwd();
const rootUrl = `${pathToFileURL(root).href}/`;
const session = new Session();
session.connect();
await session.post("Profiler.enable");
await session.post("Profiler.startPreciseCoverage", { callCount: true, detailed: true });

const findings = [];
try {
  const payments = await import(pathToFileURL(path.join(root, "src", "payments.js")).href);
  await session.post("Profiler.takePreciseCoverage"); // drops module loading
  run(payments, card);
  const cardRun = functionsRun(await session.post("Profiler.takePreciseCoverage"), rootUrl);
  const answers = run(payments, bank);
  const bankRun = functionsRun(await session.post("Profiler.takePreciseCoverage"), rootUrl);
  for (const [name, want] of Object.entries(BANK_ANSWERS)) {
    if (answers[name] !== want) findings.push(`bank ${name} gave ${JSON.stringify(answers[name])}, not ${JSON.stringify(want)}`);
  }
  const places = telling(cardRun, bankRun);
  if (places.length > 1) findings.push(`methods told apart in ${places.length} functions: ${places.join(", ")}`);
  else console.error(`probe: methods told apart in ${places.length} function(s) ${places.join(", ")}`);
} catch (error) {
  findings.push(`payments failed: ${error.message}`);
} finally {
  await session.post("Profiler.stopPreciseCoverage");
  session.disconnect();
}
for (const finding of findings) console.error(`probe: ${finding}`);
console.log(JSON.stringify({ [ID]: findings.length ? 0 : 1 }));
