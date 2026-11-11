// Customer support tickets. Dates are "YYYY-MM-DD" strings in UTC.

const URGENT_SUBJECT_RE = /\b(outage|down|cannot log in|can't log in|charged twice)\b/i;

export function ticketPriority(ticket) {
  if (ticket.plan === "business") return "urgent";
  return URGENT_SUBJECT_RE.test(ticket.subject) ? "urgent" : "normal";
}

export function sortForTriage(tickets) {
  const rank = (ticket) => (ticketPriority(ticket) === "urgent" ? 0 : 1);
  return [...tickets].sort((a, b) => rank(a) - rank(b) || a.openedOn.localeCompare(b.openedOn));
}
