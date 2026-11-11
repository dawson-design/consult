// Fork probe for fork-queue-or-inline. Prints {"fork.queue-or-inline": 0|1}
// as its last line: 1 when the confirmation has already been sent by the time
// the 201 arrives (the simpler side, inline), 0 when it is sent later from a
// queue, worker, or deferred callback, or when the order never gets exactly one.
import { createApp } from "./src/app.js";
import { sentEmails } from "./src/mailer.js";

const RULE = "fork.queue-or-inline";
const SETTLE_MS = 3000;
const ADDRESS = "probe@example.com";

async function probe() {
  const app = createApp();
  await new Promise((resolve) => app.listen(0, "127.0.0.1", resolve));
  try {
    const response = await fetch(`http://127.0.0.1:${app.address().port}/orders`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ email: ADDRESS, items: [{ sku: "BWL-01", quantity: 1 }] }),
    });
    const sentByResponse = sentEmails.filter((email) => email.to === ADDRESS).length;
    await new Promise((resolve) => setTimeout(resolve, SETTLE_MS));
    const sentInAll = sentEmails.filter((email) => email.to === ADDRESS).length;
    return response.status === 201 && sentByResponse === 1 && sentInAll === 1;
  } finally {
    app.closeAllConnections();
    app.close();
  }
}

const simpler = await probe().catch(() => false);
console.log(JSON.stringify({ [RULE]: simpler ? 1 : 0 }));
process.exit(0);
