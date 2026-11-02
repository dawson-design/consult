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
