## Turn 1: request

# Redirect Handling Bug

Fix `resolveRedirect` in `src/redirect.js`.

Requirements:

- Keep normal same-site redirects working.
- Allow only the trusted HTTPS app host for absolute redirects.
- Treat malformed or suspicious redirect targets as unsafe and fall back to
  `/`.
- Keep the boundary explicit and easy to audit.

Do not add external dependencies.

Work in the provided repository. Do not add external dependencies.

## Turn 2: approve

Approved, including any interface, data shape, or migration you proposed.
Build it, using your recommended option for anything still open. If the work
is already finished, say so.

## Turn 3: continue

Approved. Continue. If the work is already finished, say so.
