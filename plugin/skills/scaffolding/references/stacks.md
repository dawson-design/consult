# Stack presets

Use before recommending a stack for a new project at the Scaffold Decision
Gate. Each row is a house starting point; the Gate still asks the user.

- Scaffold with the framework's own generator. Check current versions and
  generator flags with `official-source-check`.
- `api-*` presets are the lightweight start for a language. `web-*` and
  `service-*` presets are heavier frameworks.
- Ktor, Axum, and Ring + Reitit have no separate service preset. Start at
  `api-*` and add service libraries through the Gate: Koin and Exposed for
  Ktor; tower-http and SeaORM or sqlx for Axum; Integrant, malli, and
  next.jdbc with HoneySQL for Ring + Reitit; OpenTelemetry for all three.
- Cloudflare Workers fits unless the app needs long-running processes,
  special networking, region or data-residency rules, Node server semantics,
  or services outside Cloudflare. Otherwise use a Node host.

| Preset | Stack | Default for | Switch to, when |
| --- | --- | --- | --- |
| `edge-api-cf-hono` | Hono on Cloudflare Workers | Fresh TypeScript web | |
| `fullstack-sveltekit` | SvelteKit, UI and server endpoints in one app | | `edge-api-cf-hono`: an API with no UI where edge latency matters. `static-site-astro`: content-heavy with little interactivity. |
| `static-site-astro` | Astro static site, hosted on Cloudflare by default | | `fullstack-sveltekit`: per-page interactivity or signed-in users. `edge-api-cf-hono` or `api-fastapi`: a backend with no UI. |
| `frontend-spa` | Alpine + HTMX rendered by the backend, or a Vite + Svelte SPA. Pairs with any backend preset as its API. | Fresh small frontend | `fullstack-sveltekit`: own routes, SSR, server endpoints, or heavy client-server data flow. |
| `api-fastapi` | FastAPI | Fresh Python web | `web-django`: admin, ORM, auth, and templates. `edge-api-cf-hono`: TypeScript-heavy work or Cloudflare-only deployment. `static-site-astro`: a content site. |
| `web-django` | Django | | `api-fastapi`: a pure API with no admin or templates. |
| `api-javalin` | Javalin | Fresh Java service | `service-spring-boot`: auto-config, starters, Actuator, or Spring Data. `service-quarkus`: fast cold start or native image. `api-ktor`: coroutine-native Kotlin. |
| `service-quarkus` | Quarkus | | `service-spring-boot`: Spring Security, Spring Data, or starters. `api-javalin`: a compact API with few concepts. |
| `service-spring-boot` | Spring Boot | | `api-javalin`: a compact API with few concepts. `service-quarkus`: cold start or native image as the main goal. |
| `api-ktor` | Ktor, coroutine-native | Fresh Kotlin service | `service-spring-boot`: Spring conventions with Kotlin source. |
| `api-sinatra` | Sinatra | Fresh Ruby service | `web-rails`: admin, Active Record, migrations, Hotwire, or mailers. |
| `web-rails` | Rails | | `api-sinatra`: a small API with no admin or templates. |
| `api-go-stdlib` | Go `net/http` ServeMux, no third-party router | Fresh Go service | `service-fiber`: Express-style middleware or FastHTTP throughput. Fiber is not `net/http`-compatible. |
| `service-fiber` | Fiber | | `api-go-stdlib`: `net/http` compatibility or shared `net/http` middleware. |
| `api-axum` | Axum on Tokio | Fresh Rust service | |
| `api-aspnet-minimal` | ASP.NET Core Minimal APIs | Fresh C# web | `web-aspnet-mvc`: controllers, model binding, Razor, or Blazor. |
| `web-aspnet-mvc` | ASP.NET Core MVC, Razor Pages, or Blazor | | `api-aspnet-minimal`: a compact API with no UI. |
| `api-giraffe` | Giraffe functional handlers | Fresh F# web | `web-saturn`: Rails-style conventions in F#. `web-aspnet-mvc`: C# MVC features. |
| `web-saturn` | Saturn | | `api-giraffe`: small functional handlers without Saturn's conventions. `web-aspnet-mvc`: C# MVC controllers or Blazor. |
| `api-plug-bandit` | Plug on Bandit | Fresh Elixir web | `web-phoenix`: LiveView, channels, mailers, or an asset pipeline. |
| `web-phoenix` | Phoenix. LiveView is the interactive default; use channels only when LiveView does not fit. | | `api-plug-bandit`: a minimal API with no LiveView, templates, or mailers. |
| `api-ring-reitit` | Ring + Reitit | Fresh Clojure service | |
