# Accessibility

Use when writing live regions, menus, tooltips, composite widgets, required
or error fields, SVG icons, focus rings, or reduced-motion and forced-colors
CSS. These are traps beyond the SKILL.md rules. Fetch criterion text live from
WCAG Understanding (https://www.w3.org/WAI/WCAG22/Understanding/) and widget
keyboard maps from the APG patterns
(https://www.w3.org/WAI/ARIA/apg/patterns/).

## Native-first traps

| Need | Use this | Avoid |
| --- | --- | --- |
| Site nav or command menu | Site nav: `<nav>` with a list of `<a>`, flyouts as link plus disclosure. Command surface: APG menu or menubar with the full arrow-key model. | `role="menu"` on site nav; menu roles without arrow-key handling |
| Tooltip | Hover and focus reveal with `aria-describedby`; `<button>` plus popover for a toggletip | `title` as the primary tooltip |
| Required indicator | `required` attribute plus visible "(required)" text | `aria-required="true"` alone |
| Field error | Visible message linked by `aria-describedby`; set `aria-invalid="true"` only after validation runs | `aria-invalid="true"` on first render |
| SVG icon | `<svg role="img" aria-label="...">`, or `aria-hidden="true"` next to visible text | SVG with no role and no label |

## Composite widgets

Default to roving `tabindex` for composite widgets. Use
`aria-activedescendant` only for a combobox with a listbox popup, where DOM
focus stays on the input. The container then needs `tabindex` and a visible
indicator that follows the active descendant.

## Focus and user preferences

- A focus ring drawn with `box-shadow` disappears in Forced Colors. Pair it
  with `outline: 2px solid transparent`, which becomes the forced ring.
- `prefers-reduced-motion: reduce`: keep subtle fades and remove parallax
  and large scale changes. Do not remove all animation, because orienting
  transforms help many vestibular users.
- `forced-colors: active`: use system colors (`Canvas`, `CanvasText`,
  `LinkText`, `ButtonFace`, `ButtonText`, `Highlight`). Do not set
  `forced-color-adjust: none` unless nothing else works.

## Live regions

- Pre-render the empty live region, or an `<output>`, in the initial HTML. A
  region injected at runtime usually drops its first announcement.
- Do not announce state ARIA already exposes: `aria-pressed`,
  `aria-expanded`, `aria-selected`, `aria-current`, and `aria-busy`. A live
  announcement on top double-fires.
- Use `aria-live="polite"` (or `role="status"`) for status, success, and
  result counts. Use `aria-live="assertive"` (or `role="alert"`) only for
  errors that block the task.
- For fast updates such as typing in a search box, announce the settled
  count ("12 results") after input pauses, not on every keystroke.
- Do not put auto-advancing carousels or marketing banners in a live region.
