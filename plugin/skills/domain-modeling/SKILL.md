---
name: domain-modeling
description: "Floors for domain data: unrepresentable illegal states, and the house rules for money and for dates and times. Use when adding or changing a record, status, or state machine, or any code that stores, compares, formats, serializes, or computes on money, dates, or times."
---

# Domain modeling

## Iron law

Illegal states are unrepresentable in the domain core.

## Rules

1. Make each invariant a type or constructor check, not a convention. A
   state machine lists its states and allowed transitions as data, and a
   transition function returns a Result for a disallowed move.
2. When the change stores, compares, formats, serializes, or computes on
   monetary amounts, read `references/money.md` first. When it does so on
   dates or times, read `references/dates.md` first.
3. Split a nullable that means both "missing" and "not loaded" into named
   states. A single independent toggle with no illegal combinations can
   stay a boolean.

## References

- `references/money.md`: read before any code that handles money.
- `references/dates.md`: read before any code that handles dates or times.
