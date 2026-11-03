# Platform Human Interface Guidelines

Use before building native or OS-adjacent apps, when deciding how much
platform fidelity a cross-platform UI needs, or when a web tool needs a
pattern Carbon lacks (menus, toolbars, undo, drag and drop).

## When to follow vs deviate

Follow the platform HIG strongly for:

- Native single-platform apps.
- Apps that compete with system apps (mail, calendar, notes, music, reminders).
- Enterprise and productivity software.
- Anything using system capabilities (Share Sheet, Siri Shortcuts, Dynamic
  Island, Live Activities, Handoff, App Intents, Widgets).

Deviate to a unified cross-platform brand when:

- Brand recognition outweighs OS fidelity (streaming, social, marketplace,
  collaboration tools).
- The product is a content-canvas pro tool (IDE, design tool, DAW).

Never rebuild these, even when deviating: native scrolling, text selection,
input methods (IME, autocorrect, predictive text), right-click and long-press
context menus, standard keyboard shortcuts, back gestures, Dynamic Type, and
Reduce Transparency.

## Web product tools: where to take patterns from

Carbon sets visuals, tokens, and grid. When Carbon has no pattern for an
interaction, take it from these pages:

- HIG patterns: feedback, undo and redo, modality, loading, searching,
  entering data, settings, drag and drop, file management.
  https://developer.apple.com/design/human-interface-guidelines/patterns
- HIG topics for tool chrome, keyboards, and writing: menus, context menus,
  toolbars, sidebars, alerts, lists and tables, keyboards, writing. Each sits
  under the same prefix, for example
  https://developer.apple.com/design/human-interface-guidelines/toolbars
- Material 3 interaction states and state layers:
  https://m3.material.io/foundations/interaction/states/overview
- Material 3 canonical layouts (list-detail, supporting pane):
  https://m3.material.io/foundations/layout/canonical-examples/overview

## Apple: Liquid Glass

Use when targeting iOS, iPadOS, macOS, watchOS, tvOS, or visionOS.

- Let content lead; controls float. Shrink tab bars on scroll; do not pin
  chrome when content is the point.
- Keep corners concentric: inner corner radius equals outer radius minus
  padding.
- Use semantic text styles and never hard-code point sizes or pick SF Text
  or Display cuts by hand. Support Dynamic Type from xSmall to AX5.
- Control size, default and minimum: 44×44 and 28×28 pt on iOS and iPadOS,
  28×28 and 20×20 pt on macOS, 60×60 and 28×28 pt on visionOS with 4 pt
  spacing.

Reference: https://developer.apple.com/design/human-interface-guidelines

## Google: Material 3 Expressive

Use when targeting Android or Wear OS.

- Use spring-based motion for gestural response, not linear duration tokens.
  https://m3.material.io/styles/motion/overview/how-it-works
- Use shape morphing for state transitions on prominent controls.
- Prefer short bottom bars and floating toolbars over heavy chrome.
- On the web, use Material Web (`@material/web`) only when a project already
  has it. Do not add it as a default dependency.

Reference: https://m3.material.io/

## Microsoft: Fluent

Use when targeting Windows, or when a Microsoft-adjacent web or native app
wants platform fidelity.

- App code uses alias tokens (`colorBrandBackground1`,
  `colorNeutralForeground1`), never the global tokens behind them.
- Use Segoe UI Variable on Windows (optical sizing on) and Segoe UI on the
  web. Native system fonts elsewhere.
- Mica is for primary long-lived surfaces. Acrylic is for transient surfaces
  only, such as menus and flyouts. They are not interchangeable.

Reference: https://fluent2.microsoft.design/

## Government design systems

For government and public-service apps, use the jurisdiction's official design
system before inventing a generic app shell.

- United States: U.S. Web Design System (USWDS):
  https://designsystem.digital.gov/
- United Kingdom: GOV.UK Design System: https://design-system.service.gov.uk/
- Canada: Canada.ca Design System: https://design.canada.ca/
- New Zealand: Govt.nz Design System: https://design-system.digital.govt.nz/

For other jurisdictions, search for the official design system or service manual
first. If none exists, use the closest public-sector pattern and note the gap.

Outside government, borrow GOV.UK's principles only ("Do less", "Be
consistent, not uniform"). Other services may not use its crown, typeface, or
colours. https://www.gov.uk/guidance/government-design-principles
