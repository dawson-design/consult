# Item Templates and Splitting

## Rule

The project's own templates and required fields win over these. Use the
sections below only where the project defines none, and keep any section a
project template adds.

These templates fix which sections exist. Write each section as plain,
impersonal statements. State a requirement as what the system must do.
Write "Checkout accepts a guest email", not "We want guests to be able to
check out".

The `#` line in each template is the item's title. Pass it as the title and
leave it out of the body.

Parent, children, blockers, estimates, and sprint live in the tracker's
fields and links, not in the body.

## Initiative

```markdown
# <Outcome, stated as the change: "Cut checkout abandonment">

## Outcome
<One or two sentences: what is different for users or the business.>

## Measure
<Metric, current value, target value, and where it is read.>

## Owner and horizon
<Owner and target quarter, under Rule 6.>

## Scope out
- <What this Initiative will not do.>
```

An Initiative holds at least two Epics. With one, it is an Epic. When it
closes, record which Rule 9 condition closed it.

## Epic

```markdown
# <One capability a user can see: "Guest checkout">

## Goal
<Who gets which capability.>

## Exit criteria
- <Two to five observable conditions for the feature as a whole.>

## Scope out
- <Work that belongs to another Epic or to no Epic.>

## Open questions
- <Question, and who answers it.>

## Links
<Design doc, ADR, or plan file.>
```

An Epic named for a category, team, or period, such as Tech debt, Platform,
or Q3, never closes. Use a label instead.

## Issue

```markdown
# <Behavior, in the imperative: "Let guests pay by card">

## Problem
<What is wrong or missing today, for whom, and what it costs them. One or
two sentences.>

## Change
<The behavior that holds once this Issue ships.>

## Acceptance criteria
- <One to five testable conditions, one per line, stated as system behavior.>

## Scope out
- <Nearby work this Issue does not do.>

## Notes
<Optional links to related code, logs, or designs. No step-by-step plan.>
```

Do not add an "As a user" story unless the project's template asks for one.
The Problem section names who has the problem and what it costs them. A
story's "As a" and "so that" clauses hold the same facts.

Write each acceptance criterion as one line. Use Given/When/Then only when a
precondition changes the result, or when the team runs BDD tests from the
criteria.

## Refactor or chore

```markdown
# <Structural change: "Move tax rules behind one module">

## Change
<What moves or is replaced, and why now.>

## Preserved behavior
<The behavior that must not change.>

## Check
<The test, query, or comparison that proves it did not change.>

## Unblocks
<The Issue or Epic this makes possible, if any.>
```

## Bug

```markdown
# <Symptom: "Checkout charges $5.00 on a $50 cart with SAVE10">

## What happens
## What should happen
## Steps to reproduce
## Environment
<Version, platform, account type, flags.>

## Acceptance criteria
- <What should happen, as an observable result. For slowness or load: the
  current measurement, the target, and how it is measured. Ask for a target
  the user did not give.>
```

Trim logs to the lines that show the fault. Rule 8's private channel is the one
`SECURITY.md` names, or a private security advisory.

A bug in a feature still in flight takes that feature's Epic as parent. A bug
in shipped behavior stands alone with the project's labels.

## Research Issue

Many teams call this a spike. It is a tracker item, not the disposable code
spike written to answer a design question.

```markdown
# Research: <Question to answer>

## Question
## Time box
<At most half a sprint.>

## Output
<The decision, where it is recorded, and the Issues drafted from it.>
```

## Approval preview

Mark every item new, existing, or changed. Name each change to an existing
item: its parent, type, title, label, or state. Mark every proposed field
value as proposed. The Rule 7 drafts file holds this preview and the full
bodies.

```text
Initiative (existing #40): Cut checkout abandonment from 18% to 12% by Q1
  Epic (new): Guest checkout
    Issue (new): Let guests pay by card without an account
    Issue (new): Send guests an order confirmation email
    Issue (new): Let guests create an account after purchase
    Issue (changed #88, parent #12 to this Epic): Keep the cart after sign-in
  Epic (new): Saved payment methods
    Issue (new): Save a card at checkout
    Research (new): Choose a vault provider for saved cards
```

## Splitting

An Issue whose body passes Rule 5's 200 words, even with the parent's context
linked, is too large. Split it.

Some work takes under half a day and changes nothing anyone can see. Put it
in the Change section of the sibling Issue that needs it.

A split into "phase 1" and "phase 2" with no behavior named for either ships
nothing.
