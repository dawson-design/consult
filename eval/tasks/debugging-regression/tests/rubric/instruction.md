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

Approved within the request as written: anything it rules out stays out.
Use your recommended option for any choice it leaves open. If you have
finished, say so.

## Turn 3: continue

Approved within the request as written. Continue with anything still
unfinished. If you have finished, say so.
