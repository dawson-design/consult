Consult is installed. Its skills load by topic, and the consult:proof skill
loads for any change that needs proving. This core applies to every code
change.

# Consult core

Uniform text is easier to scan: give every file you write one consistent
surface style.

## Rules

1. Save text files as UTF-8 without a byte order mark, with LF line endings,
   no trailing whitespace, and exactly one newline at the end of the file.
   Don't indent with tabs in a file that indents with spaces, or the reverse.
2. In JavaScript and TypeScript, end statements with semicolons and quote
   strings with double quotes. Use a template literal only when it
   interpolates a value or spans lines. Put a trailing comma after the last
   item of any list that spans more than one line, in languages that allow
   one. When the project's formatter config sets another style, follow the
   config.
4. Write numeric literals so a reader can count the digits. Separate groups
   of three in any integer of five or more digits where the language
   supports separators, as in `86_400`, and put a zero before a leading
   decimal point, as in `0.5`. Write hexadecimal digits in lowercase.
5. Order imports in three groups separated by one blank line: the standard
   library, then third-party packages, then the project's own modules.
   Alphabetize by module path within each group. Import Node built-ins with
   the `node:` prefix. When the project's linter sorts imports, its order
   wins.
7. Spell new identifiers and Markdown text in US English: `color`,
   `canceled`, `initialize`, `behavior`. Don't respell an existing name to
   match.

## House defaults

These cover Markdown files you write. Where the project's existing documents
settled a style, follow theirs.

1. **Headings:** sentence case, one level-one heading per file, and no
   skipped levels. Don't end a heading with a colon or a period.
2. **Lists:** mark unordered items with `-` and ordered items with `1.`,
   `2.`, and so on in sequence. Indent nested items by the width of the
   parent's marker. Don't mix markers within one list.
4. **Emphasis:** `**bold**` for a term on first use and `_italic_` for a
   title. Don't use emphasis in place of a heading, and don't
   bold whole sentences.
5. **Code blocks:** fence them with three backticks and a language tag, such
   as `sh`, `ts`, `json`, or `text`. Don't use indented code blocks. Put a
   shell command on its own line without a `$` prompt.
7. **Line wrapping:** wrap prose at 80 columns. Don't wrap inside a link,
   inline code, or a table row. Where the project writes one sentence per
   line, do that instead.
8. **Links:** write inline links with text that names the target, not a
   bare URL or "click here". Link to files in the repository by relative
   path.
9. **Tables:** leading and trailing pipes on every row, a separator row of
   `---`, and numeric columns right-aligned with `---:`. Use a table only
   for three or more rows.
10. **Blank lines:** one blank line before and after each heading, list,
    code block, and table. Don't use two in a row, and don't end a line with
    two spaces to force a break.
12. **Numbers:** words for one through nine and numerals for 10 and above,
    except with a unit, a version, or a percentage, which take numerals.
    Put a space between a number and its unit, as in 5 MB. Write dates in
    ISO 8601, as in 2026-03-14.
13. **Quotations:** double quotes for a quoted phrase, with closing
    punctuation outside unless it belongs to the quote. Quote a UI label
    exactly as it appears on screen.

## Markup and data files

These apply when you already edit a file of the kind; none is a reason to
create one.

1. Indent structured data with two spaces:
   - **JSON.** Keep the existing key order and add a new key at the end of
     its object. Write non-ASCII characters directly rather than as `\u`
     escapes.
   - **YAML.** Use block-style sequences and mappings. Quote a string only
     when it would otherwise parse as a number, boolean, or null.

   A formatter config in the project that covers the file overrides both.
2. In CSS, write one declaration per line with a space after the colon,
   lowercase hex colors in their shortest form, and a zero without a unit,
   as in `margin: 0`. Order a rule's declarations as layout, then box, then
   type, then color.
3. In HTML, write element and attribute names in lowercase, quote every
   attribute value with double quotes, and leave void elements such as
   `<input>` and `<br>` without a closing slash. Indent nested elements by
   two spaces.
4. In TOML, use lowercase keys with underscores, spaces around `=`, and one
   blank line before each table header. Keep an array on one line until it
   passes 80 columns.
5. In CSV, start with a header row, separate fields with commas, quote a
   field only when it holds a comma, a quote, or a line break, and double
   any quote inside a quoted field. Don't add a byte order mark.
6. In SVG, keep the `viewBox` attribute and drop a fixed `width` and
   `height` unless the image only ever shows at one size. Leave out editor
   metadata, such as Inkscape or Illustrator namespaces.
7. In XML, put the declaration on the first line, indent by two spaces, and
   write an empty element as `<name/>`. Keep attribute order as found.
8. Write a regular expression with more than one capture group using named
   groups. Don't escape a character inside a character class that needs no
   escape there.
