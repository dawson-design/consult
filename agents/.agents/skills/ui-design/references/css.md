# Modern CSS: ui-design

Browser support is a moving target: treat MDN Baseline and the linked
browser-compat tables as the source of truth before shipping production code
that depends on a newer feature.

---

## Baseline widely available: use without feature query

- Cascade layers: `@layer reset, base, tokens, layout, components, utilities;`
- Native nesting: `&` selector.
- Container queries: `@container` with `container-type: inline-size`, units
  `cqi` / `cqw` / `cqh`.
- `:has()`: relational selector.
- Subgrid.
- View Transitions Level 1: same-document SPA transitions.
- `color-mix()`.
- OKLCH and oklab.
- `light-dark()` with `color-scheme`.
- `@starting-style` with `transition-behavior: allow-discrete`: enter / exit
  from `display:none`.
- HTML Popover API: `popover`, `popovertarget`.
- `field-sizing: content`: auto-sizing inputs.
- `text-wrap: balance` on headings. `text-wrap: pretty` on paragraphs.
- `@property`: typed custom properties.
- `dvh` / `svh` / `lvh` viewport units.

---

## Use with `@supports` or progressive enhancement

Verify these features against the linked source before relying on them. Prefer
semantic fallback markup and small `@supports` blocks over browser sniffing.

| Feature                            | Production posture                                                                                               | Source anchor                                                                 |
| ---------------------------------- | ---------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------- |
| View Transitions Level 2 (MPA)     | Progressive enhancement only; same-document transitions are safer as a default.                                  | https://developer.chrome.com/docs/web-platform/view-transitions/              |
| CSS Anchor Positioning             | Useful for popovers/tooltips, but check each property/function because Baseline status can differ by subfeature. | https://developer.mozilla.org/en-US/docs/Web/CSS/Reference/Values/anchor      |
| Scroll-driven animations           | Use for non-essential motion only; provide a static layout and honor `prefers-reduced-motion`.                   | https://developer.mozilla.org/en-US/docs/Web/CSS/CSS_scroll-driven_animations |
| `interpolate-size: allow-keywords` | Enhancement for smoother intrinsic-size animation; do not make layout depend on it.                              | https://developer.mozilla.org/en-US/docs/Web/CSS/interpolate-size             |
| `@scope`                           | Good for local cascade control; verify support and remember inheritance still crosses scope boundaries.          | https://developer.mozilla.org/en-US/docs/Web/CSS/%40scope                     |
| `display: grid-lanes` (masonry)    | Experimental/early-adopter feature; do not use for critical production layout without a robust fallback.         | https://webkit.org/blog/17862/webkit-features-for-safari-26-4/                |

---

## CSS architecture

The plain-CSS renaissance is real. Nesting + layers + custom properties have
made many teams abandon runtime CSS-in-JS (incompatible with React Server
Components; bundle cost).

Current defaults:

- Tailwind CSS v4: CSS-first config via `@theme {}`, Lightning CSS engine.
  Dominates in practice. https://tailwindcss.com/
- shadcn/ui + Tailwind + CVA: default React stack. https://ui.shadcn.com/
- Vanilla Extract: zero-runtime typed styles. https://vanilla-extract.style/
- Panda CSS: https://panda-css.com/
- StyleX (Meta): https://stylexjs.com/
- CUBE CSS: BEM-style discipline at scale. https://cube.fyi/
- ITCSS: inverted-triangle organisation; maps naturally onto `@layer`.
  https://csswizardry.com/2018/11/itcss-and-skillshare/

---

## Responsive strategy

- Fluid typography via `clamp()`: Utopia approach. Replaces breakpoint-stacked
  type scales. `--step-0: clamp(1rem, 0.93rem + 0.33vi, 1.19rem);`
  https://utopia.fyi/
- Container queries: replace many media queries for component responsiveness.
- Intrinsic Web Design. Default card grid:
  `repeat(auto-fit, minmax(min(100%, 20rem), 1fr))`.
- Logical properties: `margin-inline`, `padding-block`, `inset-inline-start`.
  i18n-ready default.
- Grid for 2D page and component structure. Flex for 1D content flows.

---

## Performance rules

- **Animate only `transform`, `opacity`, `filter`.** Compositor-only. Layout
  properties are expensive every frame.
- `will-change: transform` only transiently. Remove after the animation.
- `content-visibility: auto` + `contain-intrinsic-size` for long pages.
- Inline critical CSS above the fold.
- Never animate `box-shadow` directly. Transition opacity of a pre-rendered
  shadow layer instead.
- Houdini Paint / Layout Worklets have stalled outside Chromium. Do not invest
  for cross-browser work.

---

## FLIP technique

First, Last, Invert, Play. Measure before and after, apply an inverting
transform, remove with transition.

Underlies:

- Framer Motion's `layout` prop.
- Svelte's `animate:flip`.
- Every shared-element transition library.

Ref: https://aerotwist.com/blog/flip-your-animations/

---

## View Transitions

Same-document (SPA):

```js
document.startViewTransition(() => updateDOM());
```

Cross-document (MPA, same origin only):

```css
@view-transition {
  navigation: auto;
}
```

Give shared elements matching `view-transition-name` values. The browser
interpolates position, size, opacity for free.

Customise with `::view-transition-old(name)` and `::view-transition-new(name)`
pseudo-elements.

Ref: https://developer.chrome.com/docs/web-platform/view-transitions/

---

## Motion libraries

- Motion: https://motion.dev/, successor to Framer Motion / Motion One. WAAPI
  where possible, JS fallback. React, Vue, vanilla bindings.
- GSAP: https://gsap.com/, 100% free including all former Club plugins. Use
  for timeline orchestration, scroll choreography, SVG / canvas.
- Svelte transitions: shipped in the framework. No install.
- Lottie: https://airbnb.io/lottie/, illustrative After Effects exports.
  Overkill for UI.
