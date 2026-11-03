# Link Shortener

Build a small link-shortener app. The scaffold ships only `package.json`,
a placeholder `README.md`, and a trivial smoke test.

## Requirements

### Backend

- Entry point: `src/server.js` exporting a default startup that listens on
  `process.env.PORT` (default 3000). The npm `start` script already calls
  `node --experimental-sqlite src/server.js`.
- Persist links in SQLite using the built-in `node:sqlite` module. A
  `data/links.db` file is acceptable; an in-memory DB is also acceptable
  as long as the same instance handles all requests in one process.
- Schema: at minimum `slug TEXT PRIMARY KEY`, `url TEXT NOT NULL`,
  `created_at INTEGER`, `click_count INTEGER DEFAULT 0`.

### HTTP routes

- `GET /` — HTML page with an HTMX form that POSTs to `/shorten`.
- `POST /shorten` — accepts JSON `{ "url": "..." }` *or* form-encoded
  `url=...`. Validates the URL (see Security). On success returns the
  slug; the response may be JSON `{ "slug": "...", "shortUrl": "..." }`
  or an HTMX-friendly HTML fragment, but the slug must appear in the
  response body. On rejection, return a 4xx with a useful message.
- `GET /:slug` — 302 redirect to the stored URL. Increments
  `click_count`. 404 for unknown slugs.
- `GET /admin` — HTML page listing all links and click counts.

### Frontend

- `public/index.html` — load HTMX and Alpine from CDN; HTMX form for
  creating links; show the resulting short URL inline; one Alpine
  component (e.g. copy-to-clipboard) is enough.
- `public/admin.html` (or merged into `/admin`) — list of links;
  HTMX-driven refresh is preferred but not required.

### Security

- Reject non-HTTP(S) target URLs (`javascript:`, `data:`, `file:`).
- Reject URL forms that the WHATWG URL parser leniently accepts:
  scheme without slashes (`https:host`), one slash (`https:/host`),
  scheme-relative (`//host`), backslash-prefixed, percent-encoded slash
  variants. Validate the input string form before parsing.
- Use parameterised SQL; never interpolate user input into queries.
- Slugs the server *generates* must be URL-safe (alphanumeric and `-_`).

### Tests

- Behavior tests at the seams. Both happy paths and the rejection cases
  above. Tests should boot the server (or use the exported handler /
  factory) and exercise the endpoints; do not test private helpers in
  isolation if the seam tests already cover them.

Do not add external dependencies beyond what the scaffold ships.

Work in the provided repository. Do not add external dependencies.
