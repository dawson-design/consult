# Corner Shop API

Orders for the Corner Shop's website.

```sh
npm install
npm start          # serves on PORT (default 3000)
npm test
npm run typecheck
```

Code is organized by layer: `src/controllers` validate HTTP input,
`src/services` hold business rules and throw the errors in `src/errors.ts`,
and `src/repositories` store data. Tests live in `test/`.
