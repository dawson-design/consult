## Turn 1: request

# Profile Merge Bug

Fix `mergeProfile` in `src/profile.js`.

Requirements:

- Preserve existing nested settings when a patch changes only one nested
  value.
- Keep array updates, input immutability, and plain JSON-compatible values
  predictable.
- Treat patches as untrusted JSON; the merge must not let untrusted keys
  affect global prototypes.

Do not add external dependencies.

Work in the provided repository. Do not add external dependencies.

## Turn 2: approve

Approved, including any interface, data shape, or migration you proposed.
Build it, using your recommended option for anything still open. If the work
is already finished, say so.

## Turn 3: continue

Approved. Continue. If the work is already finished, say so.
