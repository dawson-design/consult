# Typography - Frontend

Operational reference for applying Robert Bringhurst's _The Elements of
Typographic Style_ to web and product interfaces. Use this when choosing type
systems, shaping prose, setting readable measures, or deciding whether a UI's
typography is helping the user's task.

Bringhurst writes primarily from book typography. For frontend work, treat his
principles as reading-quality constraints that must be adapted to screen size,
interaction density, accessibility, localization, and live data.

## Relationship to the Frontend Canon

Bringhurst and the Swiss tradition are not competing defaults. Use them at
different levels of the same system:

- Swiss and modernist layout set the frame: grid, alignment, asymmetry,
  restraint, clear hierarchy, and deliberate whitespace.
- Bringhurst tunes the text inside that frame: measure, leading, rhythm,
  figures, punctuation, and the relationship between text and reader.
- Carbon and platform design systems set the product baseline when they apply.
  Bringhurst should refine their typography, not replace their component
  density, accessibility rules, or interaction conventions.
- Editorial, documentation, legal, and marketing prose can lean further into
  Bringhurst's book-derived reading craft.
- Dashboards, CRUD tools, admin surfaces, and repeated-use apps should keep the
  Swiss/product bias: scannability, stable alignment, compact hierarchy, and
  task speed come before classical text texture.

The practical synthesis: the grid organizes the page; typographic craft makes
the text worth reading.

## Core Stance

- Typography is content architecture, not surface styling.
- Choose type to clarify hierarchy, rhythm, reading order, and comparison.
- Design the reading conditions before polishing the visual mood.
- Product UI typography should make work scannable; editorial typography should
  make sustained reading comfortable.
- Prefer flush-left, ragged-right text for most UI and documentation. Use
  justified text only for carefully controlled editorial layouts with
  hyphenation, language metadata, and reviewed line breaks.
- A typographic rule that harms task completion, accessibility, or responsive
  behavior does not survive contact with the interface.

## Measure, Leading, and Rhythm

- Long-form body copy usually wants a measure around 45-75 characters per line;
  60-70 is a practical web default when the content is prose.
- Dense UI text, labels, nav items, form help, and table cells can be shorter.
  Do not force app surfaces into book-page line lengths.
- Longer lines need more line-height. Short labels and compact table rows need
  less, but still enough to avoid collisions across scripts and zoom levels.
- Prefer unitless `line-height` tokens so text survives font-size changes.
- Preserve vertical rhythm with spacing tokens and consistent component
  internals. Baseline grids are useful as discipline, but responsive components
  may need optical alignment instead of strict mathematical alignment.
- Use `max-width` in `ch`, grid columns, and container queries to maintain
  readable measures. Fluid type via `clamp()` is fine when the preferred value
  includes a `rem` term. Do not size text in pure `vw`, because it ignores
  browser zoom (WCAG 1.4.4).

## Type Choice

- Start with language support, legibility, x-height, weight range, numerals,
  italics, small caps, optical sizing, and loading constraints before brand
  preference.
- Use one primary interface family and one mono family for most product work.
  Add a serif only when the content is editorial, legal, academic, or otherwise
  benefits from sustained-reading texture.
- Prefer typefaces with real italics, useful weights, clear punctuation, open
  apertures, distinguishable `I/l/1` and `O/0`, and reliable rendering at UI
  sizes.
- Avoid browser-synthesized bold, italic, or small caps when quality matters. If
  the font does not include the style, choose another treatment.
- Use variable fonts and optical sizing when they improve rendering across size
  ranges, but do not expose axes as decoration.
- Traditional serif choices are legitimate for reading surfaces, but they must
  still pass the same screen-rendering, contrast, localization, and responsive
  tests as a modern sans-serif.

## Hierarchy and Scale

- Type scale follows information hierarchy, not fashion or viewport width.
- Reserve display sizes for true hero, editorial, or brand moments. Compact
  tools, panels, forms, and dashboards need smaller headings that keep the
  workflow visible.
- Create hierarchy with size, weight, position, measure, spacing, and alignment
  before relying on accent color.
- Use weight sparingly. Too many weights make hierarchy noisy and harder to
  scan.
- Do not use negative letter spacing for normal UI text. If display type needs
  tighter tracking, keep it local to large, short headings.

## Figures, Symbols, and Technical Values

- Use tabular numerals for metrics, tables, timestamps, prices, counters,
  financial values, logs, code-adjacent output, and any aligned comparison.
- Use proportional numerals for running prose when alignment is not needed.
- Use a mono face for code, identifiers, hashes, keyboard shortcuts, and raw
  technical values, but do not set full interfaces in mono for style alone.
- Use true fractions, ordinal forms, ligatures, and small caps only when they
  are supported by the font and improve comprehension.
- In data-heavy UI, favor stable character widths and fixed columns over clever
  typographic texture.

## Spacing, Punctuation, and Copy Details

- Use real typographic punctuation when the platform and content pipeline
  support it: curly quotes, apostrophes, en dashes for ranges, em dashes for
  breaks, and ellipses for omitted text.
- In code, CLI, config, logs, tests, and protocol examples, preserve literal
  ASCII exactly.
- For long prose, control widows, awkward breaks, and ragged edges where CSS
  support and content stability allow it.
- Use `hyphens: auto` only where the document language is known and browser
  dictionaries support the content well.
- Use `text-wrap: balance` for short headings and `text-wrap: pretty` for prose
  as progressive enhancement, with normal wrapping as the fallback.

## Responsive and Accessibility Constraints

- Validate type at common viewport widths, zoom levels, and dynamic text sizes.
- Text must not overlap, clip, or become unreadably compressed in controls,
  cards, tables, tabs, or sidebars.
- Maintain sufficient contrast, but remember that contrast cannot rescue poor
  size, line-height, or spacing.
- Do not encode hierarchy by color alone. Pair color with position, text,
  weight, iconography, or state.
- Check localized strings and long technical tokens. A typographic system that
  only works for short English text is unfinished.
- When accessibility, platform, or government design-system guidance conflicts
  with a classical typographic preference, the operational guidance wins.

## Practical CSS Defaults

```css
:root {
  --font-sans:
    "IBM Plex Sans", -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto,
    Oxygen, Ubuntu, Cantarell, "Helvetica Neue", Arial, sans-serif;
  --font-mono:
    "IBM Plex Mono", ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas,
    "Liberation Mono", "Courier New", monospace;

  --text-prose-measure: 66ch;
  --text-compact-measure: 42ch;
  --leading-tight: 1.2;
  --leading-ui: 1.4;
  --leading-prose: 1.6;
}

.prose {
  max-width: var(--text-prose-measure);
  line-height: var(--leading-prose);
  text-wrap: pretty;
}

.metric,
.table-number,
.timestamp {
  font-variant-numeric: tabular-nums;
}
```

## Verification

- [ ] Long-form text has a readable measure and line-height.
- [ ] Compact UI text remains scannable without oversized headings.
- [ ] Numeric comparisons use tabular numerals or otherwise align reliably.
- [ ] Type scale, spacing, and rhythm are tokenized rather than one-off values.
- [ ] Font choices cover the product's languages, symbols, weights, and states.
- [ ] No browser-synthesized typography is relied on for polished surfaces.
- [ ] Wrapping, zoom, localization, and long tokens do not break the layout.

## Sources

- Robert Bringhurst, _The Elements of Typographic Style_.
  https://www.ingramacademic.com/9780881792119/the-elements-of-typographic-style/
- Open Library edition metadata.
  https://openlibrary.org/books/OL26968509M/The_Elements_of_Typographic_Style
- Typographica review of the fourth edition.
  https://typographica.org/typography-books/the-elements-of-typographic-style-4th-edition/
- Richard Rutter, _The Elements of Typographic Style Applied to the Web_.
  https://webtypography.net/
- Matthew Butterick, _Practical Typography_.
  https://practicaltypography.com/
