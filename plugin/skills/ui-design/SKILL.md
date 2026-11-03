---
name: ui-design
description: "Frontend UI: forms, components, layout, styling, accessibility, keyboard, focus. Load before editing."
---

# UI Design

## Iron Law

`START FROM THE USER TASK AND HIERARCHY. REMOVE ANY ELEMENT THE TASK DOES NOT NEED. WCAG 2.2 AA IS THE FLOOR.`

## When to Use

- Building, changing, or reviewing any user-facing UI: layout,
  components, design systems, typography, color, motion, responsive
  behavior, forms, navigation, modals, custom controls, interactive states.
  Simple forms, single-page apps, and "just basic styling" all qualify; the
  polished-product threshold is too high a bar.
- Testing keyboard flow, focus order, screen-reader behavior, contrast,
  reduced motion, forced colors, or accessible names.

## When NOT to Use

- Backend API contracts; use `api`.
- Frontend runtime debugging or tests only; pair with `proof` and browser
  tooling.

## Rules

1. One screen has one visually dominant primary action and an information
   order that survives a squint test. Remove elements that do not improve
   comprehension, trust, or action. Use a card only to group repeated peer
   items or to frame a tool surface.
2. Define the user task, state, and flow before choosing a framework. Use
   the product's or jurisdiction's design system, else the HIG on Apple
   platforms, Material 3 on Android, and Carbon for web tools.
3. A small token system covers spacing, type, color, radius, and motion. No
   stray one-off values in committed CSS. Extend the tokens instead; only a
   browser or platform quirk gets a local value, with a comment saying why.
4. Loading, empty, error, disabled, and success states are defined with the
   layout, not later.
5. Accessibility is a design input, not a later review pass. Native HTML
   controls and semantics come before ARIA: `<button type="button">` for
   actions, `<a href>` for navigation, `<nav>` with links for site
   navigation, `<dialog>` with `.showModal()` for modals. Every interactive
   element has name, role, value, state, and keyboard behavior. A
   design-system control that already provides these may stand in for the
   native one. Where target browsers lack `<dialog>`, document the fallback.
   Visible text is the accessible name; use `aria-label` only on icon-only
   controls.
6. Focus is visible: at least a 2px outline at 3:1 contrast against both
   adjacent surfaces, with a transparent fallback for Forced Colors. Tab
   order follows DOM order; positive `tabindex` has no safe use. Focus is
   restored after a modal or overlay closes. An equivalent indicator that
   meets the same size and contrast also passes.
7. Forms have explicit labels, grouped controls, errors tied to fields, and
   no placeholder-only instructions. Dragging has a single-pointer
   alternative. Authentication never depends on a cognitive test.
8. Automated checks catch only part of the problem. Meaningful UI changes get
   manual keyboard testing, and custom controls, dialogs, menus, tabs, forms,
   and live updates get screen-reader testing. Remaining gaps are recorded as
   explicit blockers or deferred work, never left implicit.

## Handoffs

- `proof`: UI behavior tests and browser-verified flows, including
  accessibility-critical paths.
- `documentation`: design-system usage docs and accessibility statements.

## References

- `references/accessibility.md`: load before writing live regions, menus,
  tooltips, composite widgets, required or error fields, SVG icons, focus
  rings, or reduced-motion and forced-colors CSS.
- `references/canon.md`: load when choosing a framework, font, type scale,
  or spacing default, or before building a tool, dashboard, admin, or CRUD
  screen.
- `references/platforms.md`: load for native platforms, government design
  systems, or web tool patterns Carbon lacks (menus, toolbars, undo, drag
  and drop).
- `references/editorial.md`: load for brand, marketing, landing, editorial,
  release, and docs home pages, not tools.
