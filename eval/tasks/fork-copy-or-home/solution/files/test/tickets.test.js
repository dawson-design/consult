import assert from "node:assert/strict";
import test from "node:test";
import { responseDueBy, sortForTriage, ticketPriority } from "../src/tickets.js";

test("business-plan tickets and outage reports are urgent", () => {
  assert.equal(ticketPriority({ plan: "business", subject: "Invoice question" }), "urgent");
  assert.equal(ticketPriority({ plan: "free", subject: "Site is down" }), "urgent");
  assert.equal(ticketPriority({ plan: "free", subject: "Change my email" }), "normal");
});

test("triage puts urgent tickets first, oldest first within a priority", () => {
  const tickets = [
    { id: 1, plan: "free", subject: "Change my email", openedOn: "2026-03-02" },
    { id: 2, plan: "free", subject: "Outage in EU", openedOn: "2026-03-04" },
    { id: 3, plan: "business", subject: "Invoice question", openedOn: "2026-03-03" },
  ];
  assert.deepEqual(sortForTriage(tickets).map((t) => t.id), [3, 2, 1]);
});

const urgent = (openedOn) => ({ plan: "business", subject: "Invoice question", openedOn });
const normal = (openedOn) => ({ plan: "free", subject: "Change my email", openedOn });

test("an urgent ticket is due one business day after it was opened", () => {
  assert.equal(responseDueBy(urgent("2026-03-04")), "2026-03-05");
  assert.equal(responseDueBy(urgent("2026-03-06")), "2026-03-09");
});

test("a normal ticket is due three business days after it was opened", () => {
  assert.equal(responseDueBy(normal("2026-03-04")), "2026-03-09");
});

test("a ticket opened on a weekend counts from the next business day", () => {
  assert.equal(responseDueBy(urgent("2026-03-07")), "2026-03-10");
  assert.equal(responseDueBy(normal("2026-03-08")), "2026-03-12");
});

test("company holidays are not business days", () => {
  assert.equal(responseDueBy(urgent("2026-11-25")), "2026-11-27");
  assert.equal(responseDueBy(urgent("2026-11-26")), "2026-11-30");
});
