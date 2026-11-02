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
