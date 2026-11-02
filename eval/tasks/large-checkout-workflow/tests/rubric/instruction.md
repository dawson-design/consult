# Checkout Flow Maintenance

You are working in a small order service. The happy-path tests pass, but the
checkout path is starting to receive duplicate submits and partial failures in
production.

Keep the public `submitCheckout(request, services)` shape. Make the workflow
safe enough for repeated submits, stock failures, and payment failures. Preserve
the existing happy path, add the tests you need, and update the maintainer notes
with the operational behavior someone should expect.

Work in the provided repository. Do not add external dependencies.
