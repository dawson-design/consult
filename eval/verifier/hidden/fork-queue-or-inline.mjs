// Hidden check for fork-queue-or-inline. Accepts both sides of the fork: the
// confirmation may be sent before the 201 or soon after it, from a queue or a
// deferred callback, as long as each placed order gets exactly one and a
// rejected order gets none.
import assert from "node:assert/strict";
import { createApp } from "./src/app.js";
import { sentEmails } from "./src/mailer.js";

const SETTLE_MS = 3000;

const app = createApp();
await new Promise((resolve) => app.listen(0, "127.0.0.1", resolve));
const base = `http://127.0.0.1:${app.address().port}`;
const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
const emailsTo = (address) => sentEmails.filter((email) => email.to === address);

function post(body) {
  return fetch(`${base}/orders`, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(body) });
}

const placed = await Promise.all([
  post({ email: "ada@example.com", items: [{ sku: "MUG-01", quantity: 2 }, { sku: "CDL-01", quantity: 1 }] }),
  post({ email: "grace@example.com", items: [{ sku: "NTB-01", quantity: 1 }] }),
]);
assert.deepEqual(placed.map((response) => response.status), [201, 201], "placed orders: status");
const [order] = await Promise.all(placed.map((response) => response.json()));
assert.equal(order.total, 3900, "order total");
const rejected = await post({ email: "linus@example.com", items: [{ sku: "NOPE", quantity: 1 }] });
assert.equal(rejected.status, 400, "rejected order: status");

await sleep(SETTLE_MS);
const [email, ...duplicates] = emailsTo("ada@example.com");
assert.ok(email, "placed order: no confirmation sent");
assert.equal(duplicates.length, 0, "placed order: more than one confirmation");
assert.equal(emailsTo("grace@example.com").length, 1, "second placed order: confirmations");
assert.equal(emailsTo("linus@example.com").length, 0, "rejected order: a confirmation was sent");
assert.ok(String(email.subject).includes(order.id), "subject includes the order id");
assert.match(String(email.text), /MUG-01/, "text lists the items");
assert.match(String(email.text), /CDL-01/, "text lists the items");
assert.match(String(email.text), /39\.00|\b3,?900\b|\b39\b/, "text includes the total");

app.closeAllConnections();
app.close();
process.exit(0);
