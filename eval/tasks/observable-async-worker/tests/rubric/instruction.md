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

Approved, including any interface, data shape, or migration you proposed.
Build it, using your recommended option for anything still open. If the work
is already finished, say so.

## Turn 3: continue

Approved. Continue. If the work is already finished, say so.
