# Framework tradeoffs: ui-design

Opinionated picks to kick-start a scaffold. Version numbers and release dates
are not pinned here: check each project's release notes before committing.

---

## Svelte + SvelteKit: default

Current Svelte uses runes (`$state`, `$derived`, `$effect`, `$props`,
`$bindable`) as its reactivity model.

- Compile-time reactivity. No virtual DOM. Hello-world bundles in single-digit
  KB.
- SvelteKit: file-based routing (`+page.svelte`, `+page.server.ts`,
  `+layout.svelte`), SSR/SSG/edge/CSR per-route, form actions with progressive
  enhancement, typed `load` functions, adapters for Vercel, Cloudflare, Node,
  static hosts.
- Built-in animation primitives: `transition:fade|fly|slide|scale|blur`,
  `animate:flip` (FLIP built in), `crossfade` for shared-element morphs,
  `spring`/`tweened` stores.
- Scoped styles automatic. `$bindable` + types keep component APIs terse.

Tradeoffs:

- Smaller ecosystem than React. Bits UI, shadcn-svelte, Melt UI, Skeleton,
  Motion / GSAP / Lottie all work. Some libraries (notably rich-text editors)
  remain React-only.
- Smaller hiring pool than React.

Refs: https://svelte.dev/ · https://kit.svelte.dev/

---

## React + Next.js

Modern React ships Actions, `useActionState`, `useFormStatus`, `useOptimistic`,
`use()`, `ref` as a regular prop, and stable Server Components. Next.js ships
Turbopack and the React Compiler; use them.

Pick when:

- Team is already React.
- Hiring pool dictates.
- shadcn/ui + Radix + React Aria is explicitly desired.

Costs: more JS shipped than Svelte or Solid; sharp RSC / Client-Component
boundaries; hydration errors remain a common footgun.

Refs: https://react.dev/ · https://nextjs.org/

---

## Vue + Nuxt

Reasonable middle ground. Strong in APAC enterprise.

- Watch for Vapor Mode (direct DOM compilation, no virtual DOM) in Vue's
  roadmap; consult the Vue blog for its current stability tier before depending
  on it in production.

Refs: https://vuejs.org/ · https://nuxt.com/

---

## Astro

Right answer for marketing sites, blogs, documentation, content-dominant builds.

- Islands architecture ships zero JS by default.
- Embeds Svelte / React / Vue / Solid components side by side.
- Server Islands, Content Layer, native view transitions.

Refs: https://astro.build/

---

## Solid / SolidStart and Qwik / QwikCity

Pick when absolute performance or resumability matters more than ecosystem.

- Solid: fine-grained reactivity, JSX syntax, tiny bundles.
- Qwik: resumability over hydration.

Refs: https://www.solidjs.com/ · https://qwik.dev/

---

## htmx

Server-heavy CRUD apps with thin JS. HTML-over-the-wire.

Refs: https://htmx.org/

---

## Behavior-only primitive libraries

| Stack                  | Library                                                     |
| ---------------------- | ----------------------------------------------------------- |
| React                  | Radix Primitives: https://www.radix-ui.com/primitives      |
| React                  | React Aria Components: https://react-spectrum.adobe.com/   |
| React/Vue/Solid/Svelte | Ark UI: https://ark-ui.com/                                |
| Svelte                 | Melt UI: https://melt-ui.com/                              |
| Svelte                 | Bits UI: https://www.bits-ui.com/                          |
| Solid                  | Kobalte: https://kobalte.dev/                              |
| Solid                  | Corvu: https://corvu.dev/                                  |
| Any (positioning)      | Floating UI: https://floating-ui.com/                      |
| Any (positioning)      | Native CSS anchor positioning (preferred where it suffices) |

---

## Design-system catalogues to borrow from

| System               | Character                                                                                                                                  |
| -------------------- | ------------------------------------------------------------------------------------------------------------------------------------------ |
| IBM Carbon           | Preferred generic Consult product/tool reference: grid-first, IBM Plex, restrained, compact, enterprise-ready. https://carbondesignsystem.com/ |
| Shopify Polaris      | Merchant-focused. Prefer Polaris Web Components over the legacy Polaris React package. https://polaris.shopify.com/                        |
| Atlassian            | Complex PM tools. https://atlassian.design/                                                                                                |
| GitHub Primer        | Mona Sans, restrained, code-adjacent. https://primer.style/ (UI patterns: https://primer.style/product/ui-patterns)                                   |
| GOV.UK               | Philosophy only outside government ("Do less", "Be consistent, not uniform"). Non-GOV.UK services may not use its crown, typeface, or colours. https://www.gov.uk/guidance/government-design-principles |
| Vercel Geist         | Visual reference: monochrome, grid, Geist Sans and Mono. Fonts ship as `geist` on npm. https://vercel.com/geist/introduction |
| Adobe Spectrum       | Cross-platform. React Aria + React Stately. https://spectrum.adobe.com/                                                                    |
| Salesforce Lightning | Origin of "design token." https://www.lightningdesignsystem.com/                                                                           |
| Ant Design           | Comprehensive; harder to customise. https://ant.design/                                                                                    |
| shadcn/ui            | Copy-paste catalog of Radix + Tailwind + CVA recipes. Install via CLI into your repo. Customise aggressively. https://ui.shadcn.com/       |
