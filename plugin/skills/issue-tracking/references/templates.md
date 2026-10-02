# Item Templates and Splitting

Load this reference to draft any tracker item, or to split work that is too
large for one sprint.

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

An Epic is a feature with an end. Names such as Tech debt, Bugs, Misc,
Platform, or Q3 describe a category, a team, or a period, and such an Epic
never closes. Use a label for the category instead.

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
story's "As a" and "so that" clauses hold the same facts. A child Issue's
Problem can be one sentence. Link its Epic for the larger reason. Do not copy
the Epic's Goal, scope, or background into the Issue.

Write each acceptance criterion as one line. Use Given/When/Then only when a
precondition changes the result, or when the team runs BDD tests from the
criteria.

Record blockers with the tracker's dependency links. The body names only the
impact of a blocker.

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
spike that `specify` governs.

```markdown
# Research: <Question to answer>

## Question
## Time box
<At most half a sprint.>

## Output
<The decision, where it is recorded, and the Issues drafted from it.>
```

A research Issue ships no production code.

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

Signals that an Issue is too large:

- It breaks a Rule 3 size limit, or no one can estimate it.
- Its body passes Rule 5's 200 words even with the parent's context linked.
- Its title needs "and".
- No single test could show it working.

Some work takes under half a day and changes nothing anyone can see. Put it
in the Change section of the sibling Issue that needs it.

Ways to split, each producing slices a user, caller, or operator can see:

| Split by | Example |
|---|---|
| Workflow step | Search, then filter, then save a search. |
| Business rule | Flat discounts first, then percentage, then stacked. |
| Data variation | One currency first, then multi-currency. |
| Interface | Web form first, then the API, then the CLI. |
| Path | The main path first, then each failure path. |
| Unknown | A research Issue answers the question, then Issues follow. |
| Performance | Correct first, then fast enough. |

Three kinds of split produce no slice that can ship:

- by layer, such as backend, frontend, and tests
- by role, such as development and QA
- "phase 1" and "phase 2" with no behavior named for either

## Canon

- Bill Wake, [INVEST in Good Stories, and SMART Tasks](https://xp123.com/articles/invest-in-good-stories-and-smart-tasks/)
  (2003): the source of Independent, Negotiable, Valuable, Estimable, Small,
  Testable. Load when judging whether an Issue is well formed.
- Bill Wake, [Twenty Ways to Split Stories](https://xp123.com/twenty-ways-to-split-stories/)
  (2005): get a thin end-to-end path in place first.
- Richard Lawrence and Peter Green,
  [The Humanizing Work Guide to Splitting User Stories](https://www.humanizingwork.com/the-humanizing-work-guide-to-splitting-user-stories/):
  patterns for splitting, and why not to split by layer.
- Mike Cohn,
  [Five Simple but Powerful Ways to Split User Stories](https://www.mountaingoatsoftware.com/agile/five-simple-but-powerful-ways-to-split-user-stories):
  SPIDR (spikes, paths, interfaces, data, rules).
- [The Scrum Guide](https://scrumguides.org/scrum-guide.html): sprints of one
  month or less, the definition of done, and sprint scope set with the
  product owner.
