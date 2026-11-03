# Webhooks

Use this file when designing or reviewing webhook delivery from your service
to a consumer. Assume retries, replays, and out-of-order delivery.

## Signing

- Sign every payload with HMAC-SHA-256 or stronger, over the raw body bytes
  and a timestamp.
- Send the signature and timestamp in dedicated headers, and document how a
  consumer rebuilds the signed string.
- Rotate signing keys with an overlap: sign with both the old and new keys
  until consumers have moved.

## Replay Protection

- Document a timestamp window, commonly 5 minutes, and tell consumers to
  reject older deliveries.
- Send a stable event ID with every delivery, and tell consumers to drop IDs
  they have seen within the retry horizon.

## Versioning

Put a version in the event type (`invoice.created.v2`) or a top-level
`version` field. Additive changes ship as optional fields; breaking changes
ship as a new event type.

## Delivery and Retries

- Document the retry schedule (backoff, max attempts, total window), so
  consumers can size their dedupe window to match it.
- Stop retrying an endpoint that answers `410 Gone`. Keep retrying other
  failures within the schedule.
- Give consumers a way to replay missed events after an incident.
