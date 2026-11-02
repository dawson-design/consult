No code yet. Here is the shape for your approval.

## Needs your decision

- Links and click counts live in memory, so a restart loses them. Keeping them needs a database or a data file; tell me if you want that now.
- `npm run typecheck` needs `typescript` and `@types/node` as dev dependencies. I'm asking to add those two; nothing else is installed.

## Proposed shape

- Node 22 with `node:http`, no framework. The service reads only `PORT` (default 3000).
- `GET /`: the page where people paste a long URL.
- `POST /links` with `{ url }` as JSON or a form: 201 with `{ slug, shortUrl }` as JSON, or an HTML fragment for the form. 400 with `{ error }` when the body is not valid JSON or the URL is not an absolute http or https URL.
- `GET /<slug>`: 302 to the long URL, counting a click; 404 for an unknown slug.
- `GET /stats`: a JSON list of `{ slug, url, clicks }`.
- Slugs are 8 random URL-safe characters.
- The contract lives in `openapi.yaml`. `npm test`, `npm run lint`, and `npm run typecheck` check the code.
