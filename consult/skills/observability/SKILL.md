---
name: observability
description: Adding or changing production logs, metrics, traces, health checks, or alerts. Not debug prints.
---

# Observability

## Iron Law

`NO USER-REACHABLE SERVICE PATH SHIPS BLIND.`

## When to Use

- Logs, metrics, traces, health checks, dashboards, SLOs, alerts, dependency
  health, incident diagnosis, OpenTelemetry, cardinality, burn-rate alerts.
- Improving production performance; relevant metrics must be in place.

## When NOT to Use

- Local-only scripts or libraries with no operational surface.
- Error type design; use `error-handling`. Release sequencing; use `release`.

## Rules

1. Every new user-reachable path emits request, error, and duration (RED)
   signals, and traces cover its inbound and outbound boundaries. Critical
   dependencies expose latency, error, timeout, retry, circuit state, and
   saturation.
2. When improving production performance, put relevant performance metrics in
   place before changing behavior and verify their values afterward. Use
   `performance` for the baseline and comparable before/after evidence; without
   that evidence, do not claim an improvement.
3. Logs are structured events with stable names, typed fields, severity,
   outcome, and trace or correlation ID, using OpenTelemetry semantic
   conventions where they exist. Levels distinguish expected client failures
   from operator-actionable errors. Load `references/logging.md` for any
   logging change.
4. Metric labels are bounded. User IDs, request IDs, and paths go in logs or
   traces, because cardinality is a production cost.
5. Sensitive data is redacted at the source with a field allowlist (see
   `security`); collector filtering is defense in depth only.
6. Liveness never depends on external systems. Readiness does.
7. Alerts fire on user impact, SLO burn, or actionable dependency failure,
   and link to a runbook with action and escalation. Tune noisy alerts by
   signal, owner, or threshold; never silence them.
8. Dashboards answer current health and likely fault location.
9. A prototype may defer observability only if the deferral is recorded and
   the path is promoted before real users reach it.

## Tripwires

| Trigger | Do this instead | False alarm |
|---|---|---|
| "We logged the error, so it is observable" | Add stable event name, outcome, severity, and correlation ID. | The project logger adds those fields automatically and tests prove it. |
| "Put user ID / request ID / path in a metric label" | Bound the labels; put high-cardinality values in logs or traces. | The label set is proven bounded. |
| "Alert on every error" | Alert on user impact, SLO burn, or actionable dependency failure. | Low-volume critical security or data-loss event. |
| "Health check should test the database" | Keep liveness local; put dependencies in readiness. | The endpoint is explicitly readiness. |
| "The collector will redact it" | Redact at the source. | Source redaction is impossible and the risk is documented. |
| "Dashboard later" | Add the view needed to find current health and fault location. | Local-only prototype with the deferral recorded. |

## Handoffs

- `documentation`: runbook shape.
- `async-systems`: stream lag, fanout, replay, delivery semantics.
- `release`: rollout gates and production verification.
- `performance`: target measure, baseline, and comparable result.
- `error-handling`: timeout, retry, and circuit-breaker behavior.
- `security`: redaction allowlists and security-event alerts.

## References

- `references/logging.md`: load for any change to log events or fields.
