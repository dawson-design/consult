# API Evolution

Use this reference when a public HTTP API can change without a major
version if the change is additive and optional.

## Rule

An API can evolve without major versioning when existing endpoints
function as before and existing consumers can ignore the new endpoint,
field, query parameter, or header. Additions that require existing
consumers to change are breaking even if they look additive in the
schema.

## Evolutionary Changes

- Add a new endpoint.
- Add a new method to an existing path.
- Add an optional query parameter.
- Add an optional request or response field inside an object.
- Add an optional header.
- Rename a path or field by adding the successor, keeping the old
  contract, and marking the old name deprecated in OpenAPI.

## Breaking Changes

- Change the HTTP methods supported by an existing URI.
- Change status codes returned by an existing URI.
- Change the name or type of an existing request or response header.
- Make a new parameter, field, or header required.
- Remove or rename an endpoint, parameter, field, or header in place.
- Change semantics so an old request no longer means what it meant.

## Extensibility

Design response bodies for extension from the first version:

- Use unordered query parameters.
- Return arrays of errors when multiple request problems can exist.
- Prefer objects with named fields over positional arrays or flat
  scalar lists.
- Choose specific names that leave room for later distinctions, such as
  `mailingAddress` instead of `address` when another address role may
  appear.

Flat scalar lists are hard to evolve because there is nowhere to attach
new data. For example, a payment-history response that returns only an
array of IDs cannot later add payment dates without changing the item
shape. A response that returns resource objects with `id`, `type`, and
named `attributes` can add `paymentMethod` or `approvalDate` as optional
fields while old consumers continue to read the fields they know.

Adding optional pagination parameters to an unpaged collection can be
evolutionary only if the original call without those parameters still
behaves as before. If `GET /claims` used to return the full collection,
then `GET /claims?pageNumber=2&pageSize=10` can be added without a
major version only if `GET /claims` does not silently become paged.

## Versioning Strategies

When a shipped contract with independent consumers cannot be evolved in place,
ship the successor under a new version. An explicitly unstable contract may
change in place. So may one whose change no running consumer can observe. Open
browser tabs and installed apps are independent running consumers that keep
running old client code after a deploy, so shipping server and client in one
deploy does not by itself qualify.
Pick one versioning strategy per service and apply it consistently:

- **URL path** (`/v1/...`, `/v2/...`): most discoverable, simplest to
  route and cache. Major versions only; minor and patch live inside
  the same path.
- **Media type** (`application/vnd.example.v1+json`): clean
  separation but harder to debug; tools and CDNs may not vary on
  `Accept` by default.
- **Header** (`API-Version: 1`, `X-API-Version: 2024-01-15`):
  flexible but invisible in URLs and access logs unless explicitly
  captured.
- **Date-based** (`API-Version: 2024-01-15`): every breaking change
  pins a date; clients lock to a date and migrate explicitly.

Mixing strategies fragments client tooling. Document the chosen
strategy in the API reference and stick to it.

## Bumping

- Bump the major version when a shipped contract with independent consumers
  needs a breaking successor under the Evolutionary/Breaking rules above.
- Compatible additive changes never re-version; the same major can
  carry many minor additions.
- Pre-release contracts (`v0.x`, alpha, beta) may break without a
  major bump if the contract is documented as unstable.

## Overlap Windows and Sunset

Every retired version with independent consumers needs an overlap window during
which both versions serve traffic:

- Announce deprecation in API docs, response headers (`Deprecation`,
  `Sunset`), and changelog entries.
- Run the old version long enough for active consumers to migrate;
  measure adoption before removal.
- Hand the bump, CHANGELOG entry, and `Sunset`/`Deprecation` header
  scheduling to `release`.
- Remove the old contract only after the announced sunset date and
  observed traffic decline.

See RFC 8594 (`Sunset` header) and RFC 9745 (`Deprecation` header).
