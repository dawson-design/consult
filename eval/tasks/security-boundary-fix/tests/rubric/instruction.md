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

Approved within the request as written: anything it rules out stays out.
Use your recommended option for any choice it leaves open. If you have
finished, say so.

## Turn 3: continue

Approved within the request as written. Continue with anything still
unfinished. If you have finished, say so.
