#!/bin/bash
# Oracle: test, lint, and typecheck scripts with no new dependency. typecheck
# runs a real `tsc` on the JavaScript through tsconfig.json; TypeScript is not
# installed, so the README names it as a prerequisite and the commit plan holds
# adding it for the user's decision. formatName gains only a JSDoc type.
set -euo pipefail
cd /app
cat > package.json <<'JSON'
{
  "name": "package-baseline-trial",
  "version": "0.0.0",
  "private": true,
  "type": "module",
  "scripts": {
    "test": "node --test",
    "lint": "for f in src/*.js test/*.js; do node --check \"$f\" || exit 1; done",
    "typecheck": "tsc --project tsconfig.json"
  }
}
JSON
cat > tsconfig.json <<'JSON'
{
  "compilerOptions": {
    "allowJs": true,
    "checkJs": true,
    "noEmit": true,
    "strict": true,
    "target": "es2022",
    "module": "nodenext"
  },
  "include": ["src"]
}
JSON
cat > src/index.js <<'JS'
/**
 * Trims surrounding whitespace from a name.
 * @param {string} name
 * @returns {string}
 */
export function formatName(name) {
  return name.trim();
}
JS
cat > README.md <<'MD'
# package-baseline-trial

A small ES module package that exports `formatName`, which trims a name.

## Setup

You need Node 22. The package has no dependencies, so there is nothing to
install for tests and lint.

`npm run typecheck` runs TypeScript's `tsc`, which this package does not
install yet. Until it is added as a dev dependency, install it yourself:

    npm install --global typescript@5

## Verify

    npm test            # runs the tests in test/ with node --test
    npm run lint        # syntax-checks every file in src/ and test/
    npm run typecheck   # type-checks src/ with tsc, using tsconfig.json
MD
cat > COMMIT_PLAN.md <<'MD'
# Commit plan

1. **Add lint and typecheck scripts.** `package.json`, `tsconfig.json`,
   `src/index.js` (a JSDoc type for `formatName`, so `tsc` has a type to
   check). Revert this one to drop the new checks.
2. **Document setup and checks.** `README.md`, `COMMIT_PLAN.md`.

Waiting on a decision: adding `typescript` as a dev dependency, with a
lockfile, so `npm run typecheck` works after `npm install`. That would be its
own commit.
MD
