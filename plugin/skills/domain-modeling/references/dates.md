# Dates and times

Use this when storing, comparing, formatting, serializing, or computing on
dates or times. Loaded by `domain-modeling` Rule 2.

## Rules

1. Keep instants and local values as different types. An instant (a log
   entry, an expiry, a payment time) is timezone-aware and stored in UTC. A
   wall-clock value (a birthday, opening hours) uses a local date or time
   type, never a fake midnight-UTC instant.
2. Store a recurring local event ("every Tuesday at 09:00") as wall-clock
   time plus an IANA zone name, not a UTC instant. A stored UTC instant
   drifts by an hour across DST changes and when the user moves.
3. Do calendar math with a date library. "Tomorrow at the same time" is
   calendar addition, not `+ 86400` seconds, and DST makes some local times
   not exist and others happen twice.
4. Serialize instants as RFC 3339 with `Z` or an explicit offset. Use epoch
   numbers only with a documented unit, and use one format per API. Reject
   or apply a documented zone to input with no offset; never assume UTC
   silently.
5. Convert both sides to UTC before comparing or sorting instants from
   different sources. Keep locale-formatted dates out of logs, filenames,
   and keys, because they do not sort.
6. Read the current time through an injected clock, so domain code and
   tests do not depend on the real date, time zone, or weekday.

## Types

| Where | Use |
|---|---|
| Postgres | `timestamptz` for instants; `date` and `time` for local values. |
| MySQL | `DATETIME` only with an enforced UTC convention. |
| SQLite | ISO 8601 text. |
| .NET | `DateTimeOffset` for instants, never `DateTime`. |
