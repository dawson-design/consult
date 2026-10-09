# Design Canon - Frontend

Operational reference. Load when a UI task needs visual judgment, style
arbitration, or a principled explanation for layout, typography, color, motion,
or interaction. This is not a design-history survey; use it to make concrete
interface decisions.

## How to Use This Canon

Use the canon as a sequence of filters:

1. Does the screen serve the user's primary task?
2. Is hierarchy visible before reading the text?
3. Does the layout use a grid and deliberate whitespace?
4. Are typography, color, and motion restrained enough to support the work?
5. Can any element be removed without losing comprehension, trust, or action?

When a rule conflicts with an existing product, brand, platform, or government
design system, prefer the established system unless it weakens accessibility or
task completion.

## Swiss and Modernist Layout

The useful parts of Swiss design for agents:

- Start with a grid: margins, columns, gutters, and a spacing unit before
  choosing decoration.
- Align edges. A visible element should snap to the grid or to a clear optical
  alignment.
- Use flush-left, ragged-right text for most UI and documentation surfaces.
  Centered text is for short, deliberate moments, not dense tools.
- Create hierarchy with scale, weight, position, density, and whitespace before
  adding color.
- Use asymmetry with purpose. Avoid defaulting every screen to centered stacks
  or equal cards.
- Treat whitespace as structure, not leftover space.
- Prefer concrete product, data, or state over vague illustration.
- Use an 8px spacing rhythm for most web app surfaces; use 4px only for dense
  internal relationships and 16/24/32px for larger grouping.

Design-system ancestor to remember: Karl Gerstner's programmatic design maps
cleanly to modern tokens, grids, components, and variants.

## Rams Filter

Use Dieter Rams as the deletion pass:

- Useful: the design helps the user complete the job.
- Understandable: state, action, and consequence are visible.
- Honest: visuals do not imply capability, precision, or permanence the product
  does not have.
- Unobtrusive: the UI does not compete with the user's work.
- Long-lasting: patterns are durable, not trend-chasing.
- Thorough: empty, loading, error, disabled, success, and long-content states
  are handled.
- Minimal: remove the element if its absence does not damage meaning or action.

The practical rule is "less, but better": delete until deletion hurts.

## Default Product UI Baseline

When no stronger product, brand, platform, or jurisdictional system applies, use
IBM Carbon as the generic product/tool reference:

- Grid-first layout.
- Neutral palette with restrained accents.
- Compact, scannable density.
- Clear components over decorative cards.
- IBM Plex Sans for interface text, Plex Mono for code and technical values, and
  Plex Serif only for editorial or long-form explanation.

If the work is for government or public-service delivery, start from the
relevant official design system instead; see `platforms.md`.

## Typography

Pair this section with `typography.md`. Swiss modernism supplies the grid,
alignment, restraint, and product clarity; Bringhurst supplies the reading craft
inside that structure.

- Use one primary interface family and one mono family. Add a serif only when
  the content is editorial or long-form.
- Prefer IBM Plex for generic Consult product/tool UI. Inter, Geist, SF Pro, and
  well-tuned system stacks are acceptable when they better match the product or
  platform.
- Body text should usually sit around 45-75 characters per line. Dense tool
  surfaces may be shorter; long prose can be wider only with comfortable
  line-height.
- Use tabular numbers for metrics, tables, timestamps, money, and aligned
  technical values.
- Type scale follows hierarchy, not viewport width. Do not use hero-scale type
  inside compact panels, dashboards, or form tools.
- Avoid negative letter spacing on body and UI text. Large, short display
  headings may take slight negative tracking.

Useful fallback stack:

```css
font-family:
  -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Oxygen, Ubuntu,
  Cantarell, "Helvetica Neue", Arial, sans-serif;
```

## Color

- Ship a neutral ramp, one primary accent, and semantic colors for success,
  warning, error, and info.
- Use accent color for action and state, not every heading, link, and highlight.
- Check color in context. The same token changes perceptually depending on its
  neighbors.
- Avoid one-note palettes where the entire interface is just variants of one
  hue.
- Dark mode should not use pure black or pure white. Use near-black surfaces,
  softened text, and less chroma for accents.
- Use WCAG contrast thresholds as the floor; check APCA when dark mode or subtle
  text is important.

## UX Heuristics That Change Implementation

- Visibility of system status: show loading, saving, queued, failed, and synced
  states where they matter.
- Match the user's language: labels and empty states should use domain terms,
  not implementation terms.
- User control: provide undo where possible. Use confirmations only for
  destructive, irreversible, infrequent actions.
- Consistency: use established platform and product conventions before custom
  interaction patterns.
- Error prevention: constrain invalid states instead of only validating after
  submission.
- Recognition over recall: keep important options visible near the work.
- Efficiency: support repeated-use flows with keyboard, stable placement, and
  low navigation cost.
- Minimalism: every visible element should help comprehension, trust, or action.

## Motion

Use motion to explain cause and effect, not to decorate:

- Keep most UI transitions under 300ms.
- Prefer opacity and transform; avoid layout-thrashing animation.
- Use easing. Linear motion usually feels mechanical.
- Use small anticipation, stagger, or follow-through only when it clarifies
  continuity.
- Respect `prefers-reduced-motion`.
- Avoid motion that blocks task completion or hides state changes.

## Common Failure Modes

- Marketing hero used for a tool, dashboard, CRUD app, or admin surface.
- Oversized cards where a list, table, toolbar, or split pane would be clearer.
- Empty state still visible when real data exists.
- Decorative gradients, blobs, or icons added before hierarchy is solved.
- Every prominent element uses the same accent color.
- Inline backend-rendered HTML plus ad hoc JavaScript for an app that needs a
  real frontend layer.
- Text, controls, or cards resize unpredictably across responsive states.
- Buttons, table actions, and filters move between states.

## Sources Worth Remembering

- Josef Muller-Brockmann, `Grid Systems in Graphic Design`.
- Emil Ruder, `Typographie`.
- Karl Gerstner, `Designing Programmes`.
- Dieter Rams, `Ten Principles for Good Design`.
- Donald Norman, `The Design of Everyday Things`.
- Nielsen Norman Group, `10 Usability Heuristics`.
- Dan Saffer, `Microinteractions`.
- Val Head, `Designing Interface Animation`.
- IBM Carbon Design System and IBM Plex.
