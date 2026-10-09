# Accessibility

WCAG 2.2 AA is the floor. Depth reference for the rules summarised in
`SKILL.md`.

---

## POUR principles

W3C Recommendation; also published as ISO/IEC 40500. Quoted verbatim from
https://www.w3.org/TR/WCAG22/ :

> Perceivable: Information and user interface components must be
> presentable to users in ways they can perceive.
>
> Operable: User interface components and navigation must be operable.
>
> Understandable: Information and the operation of user interface must be
> understandable.
>
> Robust: Content must be robust enough that it can be interpreted reliably
> by a wide variety of user agents, including assistive technologies.

WCAG 2.2 is additive to 2.1. Removes the obsolete 4.1.1 Parsing success
criterion.

---

## New in WCAG 2.2

| Criterion | Level | Rule                                                     |
| --------- | ----- | -------------------------------------------------------- |
| 2.4.11    | AA    | Focus Not Obscured (Minimum)                             |
| 2.4.12    | AAA   | Focus Not Obscured (Enhanced)                            |
| 2.4.13    | AAA   | Focus Appearance: indicator ≥ 2 CSS px perimeter, 3 : 1 |
| 2.5.7     | AA    | Dragging Movements: single-pointer alternative required |
| 2.5.8     | AA    | Target Size Minimum: 24×24 CSS px                       |
| 3.2.6     | A     | Consistent Help                                          |
| 3.3.7     | A     | Redundant Entry                                          |
| 3.3.8     | AA    | Accessible Authentication (Minimum): no cognitive tests |
| 3.3.9     | AAA   | Accessible Authentication (Enhanced)                     |

---

## Criteria developers must internalise

| Criterion | Rule                                                                               |
| --------- | ---------------------------------------------------------------------------------- |
| 1.4.3     | Contrast 4.5 : 1 body / 3 : 1 large                                                |
| 1.4.10    | Reflow to 320 CSS px                                                               |
| 1.4.11    | Non-text Contrast 3 : 1 for UI components and graphics                             |
| 1.4.12    | Text Spacing survival: line-height 1.5×, paragraph 2×, letter 0.12em, word 0.16em |
| 2.4.7     | Focus Visible                                                                      |
| 4.1.2     | Name, Role, Value: for every custom control                                       |
| 4.1.3     | Status Messages: without focus shift                                              |

---

## WCAG 3.0 status

A Working Draft, retitled _W3C Accessibility Guidelines_ (same acronym). **Do
not use for compliance until it reaches W3C Recommendation status**: check the
W3C status page before relying on it.

Preview of structural changes:

- Outcomes replace binary success criteria.
- Bronze / Silver / Gold conformance tiers.
- Contrast method not yet chosen. The 10 September 2026 Working Draft says the
  algorithm is "yet to be determined" and no longer names APCA, which earlier
  drafts proposed.

Ref: https://www.w3.org/TR/wcag-3.0/

---

## Semantic HTML first

- `<button>` for in-page actions.
- `<a href>` for navigation.
- Native `<dialog>` with `.showModal()`: handles focus trap and `inert`
  automatically.
- `<nav>`, `<main>`, `<article>`, `<section>`, `<aside>` for landmarks.
- One `<h1>` per page. Don't skip levels.
- `<label for>` paired with `<input id>` always. Never rely on `placeholder`.
- `<fieldset>` + `<legend>` for grouped inputs.

---

## Native-first decision table

Point-of-decision lookup. Reach for the right column only when the middle column
genuinely cannot express the interaction.

| Need | Use this | Avoid |
| --- | --- | --- |
| Click action | `<button type="button">` | `<div onClick>`, `role="button"` on a span |
| Navigation to a URL | `<a href>` | `<button>` that calls `router.push`, `<div onClick>` |
| Toggle on/off (immediate effect) | `<button aria-pressed>` | `role="switch"` on a div |
| Toggle inside a form (submitted with the form) | `<input type="checkbox" role="switch">` | Custom div toggle |
| Disclosure | `<details><summary>` | div + custom JS toggling display |
| Modal | `<dialog>` + `.showModal()`; close button + Esc; do not manually trap focus | div with `role="dialog"` + custom focus trap |
| Non-modal popover | `popover` attribute, or `<dialog>` + `.show()` | div + click-outside listener |
| Native dropdown | `<select>` | Custom div listbox unless design genuinely requires it |
| Custom combobox | ARIA 1.2 pattern: `role="combobox"` on the `<input>` itself; `aria-controls` to the popup | ARIA 1.0/1.1 wrapper pattern, `aria-owns` instead of `aria-controls` |
| Tabs | APG tabs pattern when content is genuinely tab-switching | `role="tab"` on site nav |
| Site nav | `<nav>` + `<ul>` of `<a>`; flyouts as link + disclosure | `role="menu"` / `role="menubar"` on site nav |
| Application menu (toolbar, contextual command surface) | APG menu/menubar with full keyboard model | Light-touch `role="menu"` without arrow-key handling |
| Tooltip | Hover/focus reveal, `aria-describedby` to the tooltip; `<button>` + popover for toggletip | `title` attribute as primary tooltip |
| Field label | `<label for>` (or wrapping label) | `aria-label` overriding visible text; placeholder as label |
| Required indicator | `required` HTML attribute + visible "(required)" text | `aria-required="true"` only |
| Field error | Visible message linked via `aria-describedby`; set `aria-invalid="true"` only after validation runs | `aria-invalid="true"` on initial render; error text not associated with the input |
| Image (informative) | `<img alt="meaningful description">` | Empty/missing alt; "Image of..." prefix |
| Image (decorative) | `<img alt="">` | Missing `alt` attribute (screen readers will read the file path) |
| SVG icon (informative) | `<svg role="img" aria-label="...">` or `<svg aria-hidden="true">` adjacent to visible text | SVG with no role and no label |
| Status update | Pre-rendered `<output>` or live region (`aria-live="polite"`) | Late-injected DOM with `aria-live`; live regions for state already exposed by `aria-pressed/expanded/selected/current/busy` |

---

## ARIA

### The First Rule of ARIA

Quoted from https://www.w3.org/WAI/ARIA/apg/practices/read-me-first/ :

> "If you can use a native HTML element or attribute with the semantics and
> behavior you require already built in, instead of re-purposing an element and
> adding an ARIA role, state or property to make it accessible, then do so."

WebAIM Million 2026 data: home pages using ARIA average 41% more detected
accessibility errors than those without (59.1 versus 42). No ARIA is better than bad ARIA.
https://webaim.org/projects/million/

### The Five Rules

1. Prefer native HTML.
2. Don't change native semantics unless necessary.
3. All interactive ARIA must be keyboard-accessible.
4. Never put `role="presentation"` or `aria-hidden="true"` on a focusable
   element.
5. Every interactive element needs an accessible name.

### ARIA 1.2 corrections

Older blog posts and library defaults still ship outdated patterns. Treat the
following as the current shape:

- **Combobox.** ARIA 1.2 places `role="combobox"` on the `<input>` itself, with
  `aria-controls` pointing to the popup, `aria-expanded` on the input, and
  `aria-autocomplete` matching the behavior. The ARIA 1.0/1.1 wrapper pattern
  (a wrapper div with `role="combobox"` and `aria-owns` on the popup) is
  deprecated; treat any agent-generated combobox using `aria-owns` on a wrapper
  as a regression.
- **Dialog.** Native `<dialog>` + `.showModal()` does not require a manual
  focus trap. The user agent prevents tab from leaving the modal into the
  document and intentionally allows escape to browser chrome. Pre-2022 articles
  that advise building a custom focus trap are out of date. Set
  `aria-labelledby` to the dialog heading and restore focus to the invoking
  element on close. For non-modal popovers prefer the `popover` attribute or
  `<dialog>` + `.show()`.
- **`aria-activedescendant`.** Has documented VoiceOver gaps on grid and
  treegrid popups. Default to roving `tabindex` for composite widgets;
  `aria-activedescendant` is appropriate only for combobox + listbox popup
  (DOM focus stays on the input). When you do use AD, the container must have
  `tabindex` and a visual focus indicator that follows the active descendant.

### APG patterns to implement faithfully

Dialog, Combobox, Listbox, Menu / Menubar, Tabs, Accordion, Disclosure, Tooltip,
Switch, Treegrid: with their prescribed keyboard maps.

Ref: https://www.w3.org/WAI/ARIA/apg/patterns/

---

## Keyboard navigation

- `tabindex="0"` to add to natural order.
- `tabindex="-1"` for programmatically focusable only.
- **Never positive tabindex.**
- Show focus rings via `:focus-visible`, not `:focus`: `outline: none` for
  mouse is acceptable only with `:focus-visible` rings.
- Implement skip links:
  `<a class="skip-link" href="#main">Skip to main content</a>`.
- Use roving tabindex for composite widgets (tabs, listboxes, menus, radio
  groups).
- Restore focus on modal close.

### Focus indicator (WCAG 2.4.13)

A focused control needs a visible indicator whose contrasting area is at least
equivalent to a 2 CSS px solid perimeter, with at least 3:1 contrast against
both the unfocused state and the adjacent surface. Concretely:

```css
:focus-visible {
  /* Visible ring; pick a token with 3:1 against both element bg and adjacent surface. */
  /* Forced Colors repaints outline-color, so a solid outline survives as is. */
  outline: 2px solid var(--focus-ring);
  outline-offset: 2px;
}

/* Trap: Forced Colors forces box-shadow to none, so a shadow-only ring vanishes. */
.shadow-ring:focus-visible {
  box-shadow: 0 0 0 2px var(--focus-ring);
  /* Invisible normally; Forced Colors repaints it as a visible system-color ring. */
  outline: 2px solid transparent;
}
```

Do not use `outline: none` without a compliant replacement. Skip links must meet
the same contrast on their visible (focused) state.

---

## User-preference media queries

Honour these; do not override:

| Query                            | Action                                                                                                                                                                             |
| -------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `prefers-reduced-motion: reduce` | Keep subtle fades. Kill parallax, large scale changes. Do not nuke all animation: vestibular users often benefit from orienting transforms                                        |
| `prefers-color-scheme: dark`     | Theme. Provide manual override.                                                                                                                                                    |
| `prefers-contrast: more`         | Raise contrast.                                                                                                                                                                    |
| `prefers-reduced-transparency`   | Turn off backdrop blur.                                                                                                                                                            |
| `forced-colors: active`          | Windows High Contrast. Use CSS system colours: `Canvas`, `CanvasText`, `LinkText`, `ButtonFace`, `ButtonText`, `Highlight`. Never `forced-color-adjust: none` unless unavoidable. |

---

## Live regions

- **Pre-render the empty live region container in initial HTML.** Injecting the
  live region itself at runtime suppresses the first announcement on most
  screen readers; the container must already exist when the content lands.
- **Do not use a live region for state ARIA already exposes.** Screen readers
  announce `aria-pressed`, `aria-expanded`, `aria-selected`, `aria-current`,
  and `aria-busy` natively, plus button-label changes and page-title changes
  after navigation. A live announcement on top of those double-fires.
- **Politeness levels:** `aria-live="polite"` for status, success messages,
  search-result counts. `aria-live="assertive"` only for errors that block the
  user's task. `role="status"` is implicit polite; `role="alert"` is implicit
  assertive plus announce-on-insertion (interrupting; use sparingly).
- **High-frequency updates** (typing in a search box) need a manually-triggered
  "X results found" status, not a per-keystroke live region.
- **Do not** wrap auto-advancing carousels, marketing banners, or page-title
  updates in a live region.

---

## Contrast tools

- WebAIM Contrast Checker: https://webaim.org/resources/contrastchecker/
- APCA: https://apcacontrast.com/
- Chrome DevTools colour picker shows both.

---

## Assistive-tech test matrix

| Screen reader | Browser           |
| ------------- | ----------------- |
| NVDA          | Firefox, Chrome   |
| VoiceOver     | Safari            |
| TalkBack      | Chrome on Android |

Automated tools catch a bounded share of issues. Deque's 2021 published
analysis of 13,000+ first-audit page states puts axe-core at ~57%; the
conservative industry range is 30–50%; vendor-marketing claims of ~80% include
semi-automated guided tests. Always follow with manual keyboard and
screen-reader passes; the remaining gap is what automation cannot see
(meaningful labels, focus order intent, screen-reader output, keyboard model
correctness on custom widgets).

Refs:

- axe DevTools: https://www.deque.com/axe/devtools/
- WAVE: https://wave.webaim.org/
- Accessibility Insights: https://accessibilityinsights.io/

---

## Inclusive design

Microsoft's Inclusive Design: https://inclusive.microsoft.design/

Principles:

1. Recognise exclusion.
2. Learn from diversity.
3. Solve for one, extend to many.

Persona spectrum: permanent, temporary, and situational variants of every
disability. Captions (designed for Deaf users) serve people in noisy bars,
language learners, and parents with sleeping infants.

Kat Holmes, _Mismatch_ (MIT Press, 2018): the definitive text.
https://mitpress.mit.edu/9780262038881/mismatch/
