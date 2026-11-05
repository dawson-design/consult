---
name: ui-design
description: "House rules for user-facing UI: task-first hierarchy, design system choice, tokens, UI states, and a WCAG 2.2 AA floor for semantics, focus, and forms. Use when building or changing a screen, component, form, layout, or styling."
---

# UI design

## Iron law

Start from the user's task and its hierarchy, remove any element the task
doesn't need, and treat WCAG 2.2 AA as the floor.

## Rules

1. A screen has one visually dominant primary action and an information
   order that survives a squint test. Remove elements that don't improve
   comprehension, trust, or action. Use a card only to group repeated peer
   items or to frame a tool surface.
2. Define the user task, states, and flow before choosing a framework. Use
   the product's design system, else the HIG on Apple platforms, Material 3
   on Android, and Carbon for web tools.
3. A small token system covers spacing, type, color, radius, and motion. No
   one-off values in committed CSS; extend the tokens. Only a browser or
   platform quirk gets a local value, with a comment saying why.
4. Design loading, empty, error, disabled, and success states with the
   layout.
5. Native HTML before ARIA: `<button type="button">` for actions, `<a href>`
   for navigation, `<dialog>` with `.showModal()` for modals. Every
   interactive element has a name, role, value, state, and keyboard
   behavior. Visible text is the accessible name; use `aria-label` only on
   icon-only controls.
6. Focus is visible: at least a 2px outline at 3:1 contrast against both
   adjacent surfaces, with a Forced Colors fallback. Tab order follows DOM
   order, with no positive `tabindex`. Restore focus when a modal or overlay
   closes.
7. Forms have explicit labels, grouped controls, errors tied to their
   fields, and no placeholder-only instructions. Dragging has a
   single-pointer alternative. Authentication never depends on a cognitive
   test.
8. Automated checks catch only part of the problem. Test meaningful UI
   changes by keyboard, and custom controls, dialogs, menus, tabs, forms,
   and live updates with a screen reader. Report what remains untested.

## References

- `references/accessibility.md`: read before writing live regions, menus,
  tooltips, composite widgets, required or error fields, SVG icons, focus
  rings, or reduced-motion and forced-colors CSS.
- `references/canon.md`: read when choosing a framework, font, type scale,
  or spacing default, or before building a tool, dashboard, admin, or CRUD
  screen.
