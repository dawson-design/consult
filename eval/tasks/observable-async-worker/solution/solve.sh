#!/bin/bash
# Oracle: a bounded pool of `options.concurrency` lanes (default 1, the old
# serial behavior), each send retried in one place up to a fixed limit with
# jittered exponential backoff, only the failed notification resent, and an
# exhausted notification counted and named in the result instead of rejecting
# the batch. Logs are structured events with allowlisted fields. The duplicate
# risk when a failed send had in fact delivered is for the report to flag.
set -euo pipefail
cd /app
cat > src/worker.js <<'JS'
// Sends a batch of notifications with at most `options.concurrency` sends in
// flight. A failed send is retried a few times with jittered backoff; one that
// still fails is counted and named in the result, and the batch carries on.
const MAX_ATTEMPTS = 3;
const BASE_RETRY_DELAY_MS = 100;

export async function processNotifications(notifications, send, logger, options = {}) {
  const concurrency = parseConcurrency(options.concurrency);
  const startedAt = Date.now();
  logger.info("notification_batch.started", { size: notifications.length, concurrency });
  const outcomes = await mapWithConcurrency(notifications, concurrency, (notification) =>
    deliver(notification, send, logger),
  );
  const result = summarize(outcomes);
  logger.info("notification_batch.finished", {
    size: notifications.length,
    sent: result.sent,
    failed: result.failed,
    retried: result.retried,
    durationMs: Date.now() - startedAt,
  });
  return result;
}

function parseConcurrency(value) {
  if (value === undefined) return 1;
  const isPositiveInteger = Number.isInteger(value) && value >= 1;
  if (!isPositiveInteger) {
    throw new RangeError(`concurrency must be a positive integer, got ${value}`);
  }
  return value;
}

// Runs `task` over `items` with at most `limit` tasks in flight, and resolves
// once every task has finished, with results in input order.
async function mapWithConcurrency(items, limit, task) {
  const results = new Array(items.length);
  let next = 0;
  async function lane() {
    while (next < items.length) {
      const index = next++;
      results[index] = await task(items[index]);
    }
  }
  await Promise.all(Array.from({ length: Math.min(limit, items.length) }, lane));
  return results;
}

// Sends one notification, retrying only it, until it succeeds or runs out of
// attempts. Never rejects: the outcome says which happened.
async function deliver(notification, send, logger) {
  for (let attempt = 1; ; attempt++) {
    const outcome = await attemptSend(send, notification);
    if (outcome.ok) return { id: notification.id, status: "sent", attempts: attempt };
    const fields = { notificationId: notification.id, attempt, error: describeError(outcome.error) };
    if (attempt >= MAX_ATTEMPTS) {
      logger.error("notification.send_failed", fields);
      return { id: notification.id, status: "failed", attempts: attempt };
    }
    const delayMs = retryDelayMs(attempt);
    logger.warn("notification.send_retry", { ...fields, delayMs });
    await sleep(delayMs);
  }
}

async function attemptSend(send, notification) {
  try {
    await send(notification);
    return { ok: true };
  } catch (error) {
    return { ok: false, error };
  }
}

function summarize(outcomes) {
  const failedIds = outcomes.filter((outcome) => outcome.status === "failed").map((outcome) => outcome.id);
  return {
    sent: outcomes.length - failedIds.length,
    failed: failedIds.length,
    retried: outcomes.filter((outcome) => outcome.attempts > 1).length,
    failedIds,
  };
}

function retryDelayMs(attempt) {
  return Math.round(Math.random() * BASE_RETRY_DELAY_MS * 2 ** (attempt - 1));
}

function describeError(error) {
  return error instanceof Error ? error.message : String(error);
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}
JS
cat >> test/worker.test.js <<'JS'

function recordingLogger() {
  const events = [];
  const record = (level) => (event, fields) => events.push({ level, event, fields });
  return { events, info: record("info"), warn: record("warn"), error: record("error") };
}

// A send that takes a few milliseconds, tracks how many sends overlap, counts
// attempts per notification, and fails while `failures(id, attempt)` says so.
function fakeSend(failures = () => false) {
  const attempts = new Map();
  const state = { active: 0, maxActive: 0, attempts };
  state.send = async (notification) => {
    const attempt = (attempts.get(notification.id) ?? 0) + 1;
    attempts.set(notification.id, attempt);
    state.active++;
    state.maxActive = Math.max(state.maxActive, state.active);
    await new Promise((resolve) => setTimeout(resolve, 5));
    state.active--;
    if (failures(notification.id, attempt)) throw new Error("smtp unavailable");
  };
  return state;
}

const batch = (count) => Array.from({ length: count }, (_, i) => ({ id: `n${i + 1}`, to: `user${i + 1}@example.com` }));

test("never has more sends in flight than the concurrency setting", async () => {
  const fake = fakeSend();
  const result = await processNotifications(batch(6), fake.send, recordingLogger(), { concurrency: 2 });
  assert.equal(result.sent, 6);
  assert.equal(fake.maxActive, 2);
});

test("retries a temporary failure without resending the others", async () => {
  const fake = fakeSend((id, attempt) => id === "n2" && attempt === 1);
  const result = await processNotifications(batch(3), fake.send, recordingLogger(), { concurrency: 2 });
  assert.deepEqual(result, { sent: 3, failed: 0, retried: 1, failedIds: [] });
  assert.deepEqual(Object.fromEntries(fake.attempts), { n1: 1, n2: 2, n3: 1 });
});

test("reports a notification that keeps failing and still sends the rest", async () => {
  const fake = fakeSend((id) => id === "n2");
  const logger = recordingLogger();
  const result = await processNotifications(batch(3), fake.send, logger, { concurrency: 2 });
  assert.equal(result.sent, 2);
  assert.equal(result.failed, 1);
  assert.deepEqual(result.failedIds, ["n2"]);
  assert.ok(fake.attempts.get("n2") > 1, "the failing notification is retried before giving up");
  assert.equal(fake.attempts.get("n1"), 1);
  assert.equal(fake.attempts.get("n3"), 1);
  const failure = logger.events.find((entry) => entry.level === "error");
  assert.equal(failure.event, "notification.send_failed");
  assert.equal(failure.fields.notificationId, "n2");
  assert.equal(failure.fields.error, "smtp unavailable");
});

test("logs the batch lifecycle without notification contents", async () => {
  const fake = fakeSend((id, attempt) => id === "n1" && attempt === 1);
  const logger = recordingLogger();
  await processNotifications(batch(2), fake.send, logger, { concurrency: 1 });
  assert.deepEqual(
    logger.events.map(({ level, event }) => [level, event]),
    [
      ["info", "notification_batch.started"],
      ["warn", "notification.send_retry"],
      ["info", "notification_batch.finished"],
    ],
  );
  assert.equal(logger.events[1].fields.notificationId, "n1");
  assert.equal(logger.events[1].fields.attempt, 1);
  assert.deepEqual(
    { sent: logger.events[2].fields.sent, failed: logger.events[2].fields.failed },
    { sent: 2, failed: 0 },
  );
  assert.ok(!JSON.stringify(logger.events).includes("@example.com"), "recipients stay out of the logs");
});

test("rejects a concurrency that is not a positive integer before sending", async () => {
  for (const concurrency of [0, -1, 1.5]) {
    const fake = fakeSend();
    await assert.rejects(processNotifications(batch(1), fake.send, recordingLogger(), { concurrency }), RangeError);
    assert.equal(fake.attempts.size, 0);
  }
});
JS
