# Editorial and Brand Surfaces - Frontend

Operational reference for pages whose job is to present one thing with
character: editorial, brand, marketing, landing, release, and docs home pages.
Product tool screens and other pages for repeated work (dashboards, admin,
CRUD, developer tools) keep `canon.md` and `platforms.md` instead.

## Rules

1. Build the hero from one image or one typographic object. Keep the product
   name in `<title>`, the header, and the `h1`. The `h1` may sit below an
   image-only hero.
2. Use one display size and one body size. Separate them with white space, not
   extra weights or colours. Use display faces for display only, never for
   body text, navigation, or labels.
3. Align content asymmetrically to one modular grid, and use the same grid on
   every brand page.
4. Fix one element, such as the wordmark or a rule, in the same position on
   every page. Vary the layout around it.
5. Give each release, post, or artefact a stable catalogue number. Show it in
   the heading and the URL.
6. Base the visual system on a named historical reference. Use only licensed or
   public-domain material, and credit it on the page.
7. Distorted, layered, or oversized type is decoration. Hide it from assistive
   technology and repeat its meaning in readable text. Never put
   `aria-hidden` inside a focusable element or on text that forms its name.
8. Motion longer than five seconds needs a pause control.
9. Size display type with `clamp()` that includes a rem term, such as
   `clamp(2.5rem, 1rem + 6vw, 8rem)`. Check it at 200% zoom and with no
   horizontal scroll at 320 CSS px.

## Sources for Rule 6

- Peter Saville (Factory Records): the cover is one image or one typographic
  object, quoting a historical source; a printed key decodes the colour code;
  FAC catalogue numbers are the model for rule 5.
- Tomato (Underworld, _Trainspotting_ titles): text as visual material and
  texture, with process material (drafts, distortion, versions) shown as part
  of the work.
- Massimo Vignelli, _The Vignelli Canon_: one or two type sizes, weight by
  function, few typefaces, white space as the main contrast.
- Jan Tschichold, _The New Typography_: asymmetric, left-aligned
  composition; form follows the function of each text element.
- Wim Crouwel (Stedelijk identity): one modular grid across every poster, so
  each reads as part of one series.
- Otl Aicher (Munich 1972): pictograms on one construction grid and a
  restricted, named palette.
- Experimental Jetset (Whitney identity): lock the name's position and flex
  everything else. Model for rule 4.
