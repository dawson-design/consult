---
name: ui-design
description: "Frontend UI: forms, components, layout, styling, accessibility, keyboard, focus. Load before editing."
---

# UI Design

## Iron Law

`START FROM THE USER TASK AND HIERARCHY. REMOVE ANY ELEMENT THE TASK DOES NOT NEED. WCAG 2.2 AA IS THE FLOOR.`

## When to Use

- Building, changing, or reviewing any user-facing UI surface: layout,
  components, design systems, typography, color, motion, responsive
  behavior, forms, navigation, modals, custom controls, interactive states.
  Simple forms, single-page apps, and "just basic styling" all qualify; the
  polished-product threshold is too high a bar.
- Testing keyboard flow, focus order, screen-reader behavior, contrast,
  reduced motion, forced colors, or accessible names.

## When NOT to Use

- Backend API shape; use `api`.
- Frontend runtime debugging or tests only; pair with `proof` and browser
  tooling.
- Performance profiling beyond UI design choices; use `performance`.

## Rules

1. One screen has one visually dominant primary action and an information
   order that survives a squint test. Remove elements that do not improve
   comprehension, trust, or action.
2. Define the user task, state, and flow before choosing a framework. Use
   the product's or jurisdiction's design system, else the HIG on Apple
   platforms, Material 3 on Android, and Carbon for web tools.
3. A small token system covers spacing, type, color, radius, and motion. No
   stray one-off values in committed CSS.
4. Loading, empty, error, disabled, and success states are defined with the
   layout, not later.
5. Accessibility is a design input, not a later review pass. Native HTML
   controls and semantics come before ARIA: `<button type="button">` for
   actions, `<a href>` for navigation, `<nav>` with links for site
   navigation, `<dialog>` with `.showModal()` for modals. Every interactive
   element has name, role, value, state, and keyboard behavior.
6. Focus is visible: at least a 2px outline at 3:1 contrast against both
   adjacent surfaces, with a transparent fallback for Forced Colors. Tab
   order follows DOM order; positive `tabindex` has no safe use. Focus is
   restored after a modal or overlay closes.
7. Color is never the only signal. Text and non-text contrast, target size,
   and reflow meet WCAG 2.2 AA. Reduced motion, forced colors, high
   contrast, and dark mode follow user preferences.
8. Forms have explicit labels, grouped controls, errors tied to fields, and
   no placeholder-only instructions. Dragging has a single-pointer
   alternative. Authentication never depends on a cognitive test.
9. Automated checks catch only part of the problem. Meaningful UI changes get
   manual keyboard testing, and custom controls, dialogs, menus, tabs, forms,
   and live updates get screen-reader testing. Remaining gaps are recorded as
   explicit blockers or deferred work, never left implicit.

## Tripwires

| Trigger | Do this instead | False alarm |
|---|---|---|
| "Add a card/section so it looks richer" | Start from the user task and hierarchy. | The card groups repeated peer items or frames a real tool surface. |
| "We'll add loading/error/empty states later" | Define the required states with the layout. | The component cannot load, fail, or be empty. |
| "One-off spacing fixes this screen" | Use or extend the token system. | A browser or platform quirk needs a documented local fix. |
| "A styled div works as a button" | Use the native control. | A design-system control that already proves semantics and keyboard behavior. |
| "Hand-roll the modal focus trap" | Use native `<dialog>` and `.showModal()`. | Target browsers lack `<dialog>` support and the fallback is documented. |
| "Remove the ugly focus outline" | Replace `outline: none` with a measured 2px outline and Forced Colors fallback. | An equivalent focus indicator meeting contrast is applied. |
| "Add an `aria-label` to be safe" | Keep visible text as the accessible name; `aria-label` only for icon-only controls. | The control is icon-only. |
| "Fix the order with `tabindex='1'`" | Fix tab order by DOM order. | None. |

## Handoffs

- `proof`: UI behavior tests and browser-verified flows, including
  accessibility-critical paths.
- `performance`: measured Core Web Vitals or rendering regressions.
- `documentation`: design-system usage docs and accessibility statements.

## References

- `references/accessibility.md`: load when the diff touches focus, dialogs,
  ARIA, forms, live regions, or a WCAG criterion you need to quote.
- `references/canon.md`: load when choosing product or tool defaults, or
  reviewing a screen against common failure modes.
- `references/typography.md`: load when setting type scale, measure, or
  rhythm.
- `references/css.md`: load when a layout or interaction is about to reach
  for JavaScript that modern CSS can do.
- `references/frameworks.md`: load when the user asks to compare frontend
  frameworks.
- `references/platforms.md`: load for native platforms, government design
  systems, or web patterns Carbon lacks.
- `references/editorial.md`: load for brand, editorial, and release pages,
  not tools.
