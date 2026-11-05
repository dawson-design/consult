# Product Defaults and Failure Modes

Use when choosing a framework, font, type scale, or spacing default, or
before building a tool, dashboard, admin, or CRUD screen.

## House Defaults

- Spacing: an 8px rhythm for most web app surfaces. Use 4px only for dense
  internal relationships, and 16, 24, or 32px for larger groups.
- Density: compact and scannable for tools. Prefer lists, tables, toolbars,
  and split panes to decorative cards.
- Fonts: one interface family and one mono family. Add a serif only for
  editorial or long-form content. Prefer IBM Plex Sans for interface text,
  Plex Mono for code and technical values, and Plex Serif for long-form
  explanation. Inter, Geist, SF Pro, and well-tuned system stacks are fine
  when they better match the product or platform.
- Frontend framework: SvelteKit for larger apps. Use htmx for small or
  server-heavy CRUD frontends with thin JavaScript, and Astro for content
  sites such as marketing pages, blogs, and docs. Use React with Next.js only
  when the user asks, the repo or team already uses React, or a React-only
  library is required, and turn on the React Compiler there.
- Prefer native HTML and CSS to JavaScript where the browser targets allow,
  such as the `popover` attribute and CSS anchor positioning over Floating
  UI.

## Typography

- Type scale follows hierarchy, not viewport width. Do not use hero-scale
  type inside compact panels, dashboards, or form tools.
- Do not use negative letter spacing on UI text.
- Load every weight, style, and script subset the UI uses. Never rely on
  browser-synthesized bold, italic, or small caps; if the font lacks a
  style, use another treatment.
- Set code, identifiers, hashes, shortcuts, and raw technical values in a
  mono face that tells `I/l/1` and `O/0` apart. Never set a whole interface
  in mono for style.
- Use typographic quotes, apostrophes, and en dashes in prose. Keep literal
  ASCII in code, CLI, config, log, and test examples.
- Check localized strings and long unbroken tokens such as hashes and URLs.
  Text must not clip, overlap, or overflow cells, tabs, or sidebars.

## Common Failure Modes

- Marketing hero used for a tool, dashboard, CRUD app, or admin surface.
- Oversized cards where a list, table, toolbar, or split pane would be
  clearer.
- Empty state still visible when real data exists.
- Decorative gradients, blobs, or icons added before hierarchy is solved.
- Visuals that imply capability, precision, or permanence the product does
  not have.
- A palette that is only variants of one hue, or one accent color on every
  prominent element. Keep the accent for action and state.
- Dark mode that keeps light-mode accent chroma. Lower the chroma.
- Labels and empty states in implementation terms instead of the user's
  domain terms.
- A confirmation dialog where undo would work. Confirm only destructive,
  irreversible, infrequent actions.
- Validation only after submission where the control could constrain the
  input instead.
- Inline backend-rendered HTML plus ad hoc JavaScript for an app that needs a
  real frontend layer.
- Text, controls, or cards that resize unpredictably across responsive
  states.
- Buttons, table actions, and filters that move between states.
