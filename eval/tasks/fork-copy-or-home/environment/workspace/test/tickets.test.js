import assert from "node:assert/strict";
import test from "node:test";
import { sortForTriage, ticketPriority } from "../src/tickets.js";

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
