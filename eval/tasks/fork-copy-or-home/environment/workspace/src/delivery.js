// Delivery estimates for orders. Dates are "YYYY-MM-DD" strings in UTC.

// The warehouse ships, and carriers deliver, on business days only: weekdays
// that are not company holidays.
const WEEKEND_DAYS = new Set([0, 6]); // Sunday and Saturday
const HOLIDAYS = new Set(["2026-01-01", "2026-05-25", "2026-07-03", "2026-09-07", "2026-11-26", "2026-12-25"]);

const TRANSIT_DAYS = { standard: 5, express: 2 };

function nextDay(date) {
  const day = new Date(`${date}T00:00:00Z`);
  day.setUTCDate(day.getUTCDate() + 1);
  return day.toISOString().slice(0, 10);
}

function isBusinessDay(date) {
  const weekday = new Date(`${date}T00:00:00Z`).getUTCDay();
  return !WEEKEND_DAYS.has(weekday) && !HOLIDAYS.has(date);
}

function addBusinessDays(date, count) {
  let current = date;
  let left = count;
  while (left > 0) {
    current = nextDay(current);
    if (isBusinessDay(current)) left -= 1;
  }
  return current;
}

export function estimateDelivery(order) {
  const transit = TRANSIT_DAYS[order.shipping];
  if (transit === undefined) throw new RangeError(`unknown shipping option: ${order.shipping}`);
  return addBusinessDays(order.placedOn, transit);
}
