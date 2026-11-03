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
