# Removals and Replacements

Use this when a change removes or replaces old code or a contract.

The proof target is the current behavior, not the old code. Prefer this
order:

1. Delete or update tests, docs, examples, commands, and references that named
   the removed code or contract.
2. Add or update tests only for the behavior that remains or replaces it.
3. Run existing boundary tests that would fail if supported callers still
   depended on the removed code or contract.
4. Use targeted search to prove stale references were removed.

Add a new absence test only when rejection is itself the surviving public
behavior: a security denylist, authorization block, explicit API rejection,
compatibility error, or migration guard with an owner and removal condition.
