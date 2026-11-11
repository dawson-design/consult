// Customer support tickets. Dates are "YYYY-MM-DD" strings in UTC.

const URGENT_SUBJECT_RE = /\b(outage|down|cannot log in|can't log in|charged twice)\b/i;
const RESPONSE_BUSINESS_DAYS = { urgent: 1, normal: 3 };

// Support works the same days as the warehouse: weekdays that are not company holidays.
const SUPPORT_HOLIDAYS = new Set(["2026-01-01", "2026-05-25", "2026-07-03", "2026-09-07", "2026-11-26", "2026-12-25"]);

export function ticketPriority(ticket) {
  if (ticket.plan === "business") return "urgent";
  return URGENT_SUBJECT_RE.test(ticket.subject) ? "urgent" : "normal";
}

export function sortForTriage(tickets) {
  const rank = (ticket) => (ticketPriority(ticket) === "urgent" ? 0 : 1);
  return [...tickets].sort((a, b) => rank(a) - rank(b) || a.openedOn.localeCompare(b.openedOn));
}

function plusOneDay(date) {
  const day = new Date(`${date}T00:00:00Z`);
  day.setUTCDate(day.getUTCDate() + 1);
  return day.toISOString().slice(0, 10);
}

function isSupportDay(date) {
  const weekday = new Date(`${date}T00:00:00Z`).getUTCDay();
  return weekday !== 0 && weekday !== 6 && !SUPPORT_HOLIDAYS.has(date);
}

export function responseDueBy(ticket) {
  let due = ticket.openedOn;
  while (!isSupportDay(due)) due = plusOneDay(due);
  for (let left = RESPONSE_BUSINESS_DAYS[ticketPriority(ticket)]; left > 0; ) {
    due = plusOneDay(due);
    if (isSupportDay(due)) left -= 1;
  }
  return due;
}
