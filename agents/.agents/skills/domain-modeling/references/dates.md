# Dates and times

Use this when storing, comparing, formatting, serialising, or computing
on dates or times: at the language, wire, database, or display layer.
Loaded by `domain-modeling` Rule 11.

## Iron rules

1. **Always timezone-aware.** Naive datetimes (no tz attached) are
   ambiguous and a source of silent bugs. They are acceptable only
   for genuinely wall-clock-only values (a birthday, "school starts
   at 09:00"), and even then, prefer a distinct type that says so.
2. Store and compute in UTC. Convert to local time only at the
   user-facing boundary (UI, scheduled-reminder evaluation). Logs,
   APIs, databases, and message payloads stay UTC.
3. Serialise as ISO 8601 / RFC 3339. `2026-04-25T12:34:56Z` is
   unambiguous; `04/25/2026` is not.
4. Use a date library. Never do date math on strings or epochs.
   Calendar arithmetic involves DST, leap years/seconds, month
   lengths, and locale-specific weeks: none of which obey
   `n_days * 86400`.
5. Distinguish instants from wall-clock-only values. An instant
   in time (UTC moment) and a wall-clock value (`LocalDate`,
   `LocalTime`, `LocalDateTime`) are different types and should be
   represented as such.

## Storage / wire / display

| Layer | Default |
|---|---|
| Database | `TIMESTAMP WITH TIME ZONE` (Postgres `TIMESTAMPTZ`); MySQL `DATETIME` only with an enforced UTC convention; SQLite stores text: pick ISO 8601. For wall-clock-only values use `DATE` / `TIME` / `LocalDate` types. |
| Wire / API / log | RFC 3339 string with `Z` or explicit offset. Epoch seconds/millis acceptable for high-throughput protocols, but document the unit. Mixing string and numeric formats in one API is a finding. |
| Domain code | The language's tz-aware type: Python `datetime` with `tzinfo=UTC`; JS `Date` is fine for instants but lacks tz semantics: prefer Temporal (Stage 4 in 2026) or `Luxon`/`date-fns-tz`; Rust `chrono::DateTime<Utc>` or `jiff`; Java/Kotlin `Instant` / `ZonedDateTime`; Ruby `Time.now.utc` / `ActiveSupport::TimeWithZone`; .NET `DateTimeOffset` (never `DateTime` for instants). |
| Display | Locale-aware formatting at the UI edge: `Intl.DateTimeFormat`, ICU, `Locale.format`. Never inject locale-specific strings into logs, APIs, or filenames. |

## High-signal review checks

- `datetime.now()` / `Time.now` / `LocalDateTime.now()` without a
  timezone is a finding. Use `datetime.now(UTC)`,
  `Time.now.utc`, `ZonedDateTime.now(ZoneOffset.UTC)`,
  `DateTimeOffset.UtcNow`.
- Comparing two datetimes with different (or unknown) timezones:
  convert both to UTC first.
- Adding seconds/minutes/days by multiplying: works for *durations*
  (`Duration.ofMinutes(5)`), breaks across DST for "tomorrow at the
  same wall-clock time."
- "Every Tuesday at 09:00 in the user's timezone" needs a
  timezone-aware schedule, not a stored UTC instant. The user moves
  cities; the cron doesn't.
- Storing a date as an integer (days since epoch / `YYYYMMDD`):
  fine if the column type or wrapper makes the unit obvious; a bare
  `int` in an API is a smell.
- Locale-formatted dates in logs, filenames, or DB rows: they break
  searches and tooling. Logs are for machines first.
- Mixing `DateTime` (no offset) with `DateTimeOffset` in C#, or
  `Date` (legacy) with `Instant` in Java, in the same call chain.
- Test fixtures that bake in "today" via a real call to
  `datetime.now()`: flaky around midnight; inject a clock.
- Server clock drift / NTP sync assumptions: rate limits,
  signatures, JWTs that depend on `now()` need monotonic + wall
  clock distinguished.
- Leap second handling: most code can assume no leap seconds (Linux
  and most OSes smear); audit when you depend on millisecond
  ordering across boundaries.

## Anti-patterns / red flags

- `datetime.now()` (Python), `new Date()` for "now" without UTC
  intent (JS), `Time.now` (Ruby) in domain code without `.utc`,
  `LocalDateTime.now()` (Java) for an instant.
- `DateTime.Now` in C# domain code: use `DateTimeOffset.UtcNow` and
  inject an `IClock` for testability.
- String-built date math: `"%s-%s-%s" % (year, month, day)` then
  parsing.
- `time.sleep(86400)` for "one day" (DST + leap second).
- Storing `2026-04-25 12:00` in a `TIMESTAMP` column with no
  timezone convention documented.
- `==` between two datetimes from different sources without
  converting to UTC first.
- Filename / log key built from local-time formatting
  (`2026-04-25-09:00`): non-sortable across timezones.
- Test that passes Mon–Sat and fails on Sundays (or in a different
  TZ) because of a `weekday()` check on `now()`.
- A user-supplied date string parsed without a timezone,
  re-serialised as if it were UTC.

## Sources

- ISO 8601: <https://en.wikipedia.org/wiki/ISO_8601>
- RFC 3339 (Internet date/time): <https://www.rfc-editor.org/rfc/rfc3339>
- "Falsehoods programmers believe about time":
  <https://infiniteundo.com/post/25326999628/falsehoods-programmers-believe-about-time>
- IANA Time Zone Database: <https://www.iana.org/time-zones>
- PostgreSQL date/time types:
  <https://www.postgresql.org/docs/current/datatype-datetime.html>
- TC39 Temporal proposal: <https://tc39.es/proposal-temporal/>
