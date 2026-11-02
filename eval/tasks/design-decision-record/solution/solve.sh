#!/bin/bash
# Oracle: one decision note, marked proposed because the team has not agreed.
# Request input is parsed once where it enters checkout; the cart helper gets
# only the checked shape. No code, package, or test changes.
set -euo pipefail
cd /app
cat > docs/checkout-validation.md <<'MD'
# Where should checkout validation live?

Status: proposed. The team has not approved this yet.

## Context

`docs/checkout-notes.md` says checkout validates some fields in the route
handler and some in the cart helper, and that the next change needs one agreed
location. The route handler and the cart helper are not in this repository,
so this note does not know which fields each place checks today. Confirm that
list before building.

With checks in two places, a rule can be added to one place and missed in the
other, and the cart helper cannot tell whether its input was checked.

## Decision

Validate checkout input once, where the request enters. The route handler
first calls one checkout parse function. That function either returns a
checked checkout request or a validation failure. It is the only code that
reads the raw request body.

The cart helper takes only the checked checkout request. It may assume every
required field is present and has the right type and range. It must not
re-check request fields, and it must not receive the raw body.

Checks that need cart or catalog state, such as stock, are cart rules, not
input validation. They stay in the cart helper, and the parse function does
not repeat them.

On a validation failure the route returns a 400 that names the failing field.
The error body and codes should match whatever checkout returns for errors
today; confirming that is a follow-up.

## Alternatives considered

- **Validate in the cart helper.** Rejected: the route would pass the raw body
  inward, every caller of the helper would have to hand it unchecked data, and
  the route would have to translate cart errors back into request errors.
- **Keep checks in both places.** Rejected: this is today's split. The two
  copies drift, and nobody knows which one is the rule.
- **Shared validation middleware.** Rejected: checkout's rules are specific to
  one route, and middleware would hide them from someone reading the checkout
  route.

## Consequences and follow-up

- The route handler gains one parse step, and the cart helper's input becomes
  the checked checkout request.
- The next pass moves the field checks out of the cart helper into the parse
  function and deletes the copies.
- Tests: route-level tests that send each kind of invalid checkout input and
  check the 400 response, and cart helper tests that pass a checked request.
- Open: the exact field list (see Context) and the error codes for each
  failure.
MD
