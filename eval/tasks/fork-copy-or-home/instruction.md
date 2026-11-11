# Response deadlines for support tickets

Support is publishing response times, and every ticket needs a due date.

Add `responseDueBy(ticket)` to `src/tickets.js`. It returns the date, as a
"YYYY-MM-DD" string, by which the ticket needs its first reply:

- An urgent ticket is due 1 business day after it was opened; a normal
  ticket is due 3 business days after.
- A ticket opened on a day that is not a business day counts as opened on
  the next business day.
- Business days mean the same thing they do for delivery estimates.

A ticket's priority comes from `ticketPriority`, and the day it was opened is
its `openedOn` field.

Work in the provided repository. Do not add external dependencies.
