# Middleware vs. Handler

Use this reference when deciding whether request behavior belongs in
middleware, an edge/gateway, or the endpoint handler.

## Rule

Move behavior into middleware only when it is a transport-wide
request-pipeline concern with the same rule for many routes. Keep
endpoint-specific validation, resource ownership, privileged
authorisation, and domain invariants in handlers or domain code where
the specific resource, actor, and contract are visible.

## Belongs in Middleware

- Request IDs and correlation propagation.
- Logging, tracing, and metrics that apply to every route.
- CORS preflight, CSP, HSTS, and other transport security headers.
- Body parsing and content negotiation.
- Authentication context establishment (who is the consumer?).
- Coarse rate limiting (global per-IP, global per-key).
- Final error-shape translation (Problem Details normalization).

Middleware may reject requests that fail a global gate (malformed
body, missing auth context). Beyond that, hand off to the handler.

## Belongs in the Handler

- Endpoint-specific input validation (this resource accepts these
  fields).
- Resource ownership checks (does this user own this object?).
- Privileged authorisation (can this user perform this action on
  this object?).
- Domain invariants (does this state transition violate the model?).
- Endpoint-specific rate or quota limits.

## Placement Test

Ask: would a different endpoint applying the same logic produce a
different correct answer? If yes, the logic depends on
endpoint-specific context and belongs in the handler. If no, it is
transport-wide and middleware-eligible.

## Anti-pattern: Authorisation in Middleware

Middleware can establish *who* the consumer is (authentication).
Deciding *what* they can do on a specific resource (authorisation)
needs the resource and the action, which the middleware does not own.
Putting authorisation in middleware scatters access rules across the
request pipeline and produces ambient-authority bugs when routes are
added or moved. Keep authorisation at the handler/domain boundary.
