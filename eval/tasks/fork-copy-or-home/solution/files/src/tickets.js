// Customer support tickets. Dates are "YYYY-MM-DD" strings in UTC.
import { addBusinessDays, isBusinessDay } from "./delivery.js";

const URGENT_SUBJECT_RE = /\b(outage|down|cannot log in|can't log in|charged twice)\b/i;
const RESPONSE_BUSINESS_DAYS = { urgent: 1, normal: 3 };

export function ticketPriority(ticket) {
  if (ticket.plan === "business") return "urgent";
  return URGENT_SUBJECT_RE.test(ticket.subject) ? "urgent" : "normal";
}

export function sortForTriage(tickets) {
  const rank = (ticket) => (ticketPriority(ticket) === "urgent" ? 0 : 1);
  return [...tickets].sort((a, b) => rank(a) - rank(b) || a.openedOn.localeCompare(b.openedOn));
}

/** The first business day on or after the day the ticket was opened, plus its priority's allowance. */
export function responseDueBy(ticket) {
  const opened = isBusinessDay(ticket.openedOn) ? ticket.openedOn : addBusinessDays(ticket.openedOn, 1);
  return addBusinessDays(opened, RESPONSE_BUSINESS_DAYS[ticketPriority(ticket)]);
}
