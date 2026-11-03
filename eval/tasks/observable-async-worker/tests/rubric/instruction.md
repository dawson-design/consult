## Turn 1: request

# Notification Worker Bug

Fix `processNotifications` in `src/worker.js`.

Requirements:

- Keep batch throughput bounded by the caller's concurrency setting.
- Handle a temporary send failure without losing the notification or sending
  duplicates.
- Return useful delivery counts and emit enough lifecycle logs to debug a
  batch.

Do not add external dependencies.

Work in the provided repository. Do not add external dependencies.

## Turn 2: approve

Approved within the request as written: anything it rules out stays out.
Use your recommended option for any choice it leaves open. If you have
finished, say so.

## Turn 3: continue

Approved within the request as written. Continue with anything still
unfinished. If you have finished, say so.
