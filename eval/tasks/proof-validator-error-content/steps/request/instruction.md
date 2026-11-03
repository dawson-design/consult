# Signup Validator

Build `validateSignup(input)` in `src/signup.js`.

Input fields:

- `email`: must be a syntactically valid email address.
- `password`: at least 8 characters, must contain mixed case and at least
  one digit.
- `age`: integer between 13 and 120 inclusive.
- `country`: ISO 3166-1 alpha-2 (two uppercase letters).

Returns:

- On success: `{ ok: true, value: input }`.
- On failure: `{ ok: false, errors: { <field>: "<message>", ... } }`.

Each error message must be a clear string a user can act on. Multiple
fields may fail at once; report every failure in `errors`, keyed by field
name.

Add tests.

Do not add external dependencies.

Work in the provided repository. Do not add external dependencies.
