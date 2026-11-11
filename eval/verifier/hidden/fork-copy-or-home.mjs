// Hidden check for fork-copy-or-home: responseDueBy counts business days the way
// delivery estimates do, and delivery estimates still work. Either side of the
// fork passes: calling the delivery module's rule, or a second copy of it.
import assert from "node:assert/strict";
import { estimateDelivery } from "./src/delivery.js";
import { responseDueBy, ticketPriority } from "./src/tickets.js";

const urgent = (openedOn) => ({ id: `u-${openedOn}`, plan: "business", subject: "Invoice question", openedOn });
const normal = (openedOn) => ({ id: `n-${openedOn}`, plan: "free", subject: "Change my email", openedOn });
assert.equal(ticketPriority(urgent("2026-03-04")), "urgent");
assert.equal(ticketPriority(normal("2026-03-04")), "normal");

const cases = [
  [urgent("2026-03-04"), "2026-03-05"], // Wednesday
  [urgent("2026-03-06"), "2026-03-09"], // Friday, over the weekend
  [normal("2026-03-04"), "2026-03-09"],
  [urgent("2026-03-07"), "2026-03-10"], // Saturday counts as Monday
  [normal("2026-03-08"), "2026-03-12"], // Sunday counts as Monday
  [urgent("2026-11-25"), "2026-11-27"], // over Thanksgiving
  [urgent("2026-11-26"), "2026-11-30"], // opened on Thanksgiving
  [normal("2026-11-24"), "2026-11-30"],
  [normal("2026-12-23"), "2026-12-29"], // over Christmas
  [urgent("2026-12-25"), "2026-12-29"], // opened on Christmas
  [urgent("2026-05-23"), "2026-05-27"], // Saturday before Memorial Day
  [normal("2026-07-02"), "2026-07-08"], // over July 3 and the weekend
];
for (const [ticket, due] of cases) {
  assert.equal(responseDueBy(ticket), due, `${ticket.plan} ticket opened ${ticket.openedOn}`);
}

assert.equal(estimateDelivery({ placedOn: "2026-03-02", shipping: "standard" }), "2026-03-09");
assert.equal(estimateDelivery({ placedOn: "2026-11-24", shipping: "express" }), "2026-11-27");
assert.equal(estimateDelivery({ placedOn: "2026-12-24", shipping: "express" }), "2026-12-29");
