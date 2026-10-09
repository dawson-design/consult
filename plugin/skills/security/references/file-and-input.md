# File upload, parsing, and input traps

Reference for the `security` skill. The high-impact bugs that come from
deserialising, unpacking, or persisting untrusted bytes.

## File upload

- Magic-byte check. Validate file content type by reading the first bytes
  with a maintained file-type detector; never trust `Content-Type` or
  extension alone. Reject anything that does not match the declared type.
- Re-encode where possible. Server-side re-encode images (resize, drop
  EXIF, normalise format) to strip smuggled scripts and PDFs. For documents,
  convert to a known format.
- Serve from a separate, cookieless origin. A stored XSS in an uploaded
  SVG cannot reach the session cookie of the main app if the file is served
  from `usercontent.example.net`.
- Force `Content-Disposition: attachment` for any type the user did not
  explicitly choose to render inline.
- Block executable content types by default: SVG, HTML, XHTML, and
  archives the app does not need to extract.
- Size limits enforced at the proxy / server **before** buffering in
  memory. The application limit is too late.
- Antivirus / content scan for risky types in regulated environments.
  ClamAV in a sidecar is the cheap baseline. Prove the scanner is wired in
  by uploading the EICAR antivirus test file and asserting rejection.
- Random storage names. Never use the user-supplied filename as the
  storage path. Map to a UUID; keep the original name only in metadata.
- MIME-sniffing defence. Send `X-Content-Type-Options: nosniff` and
  serve with the correct `Content-Type`.

## Path traversal

- Canonicalise (`realpath`, `Path.resolve`) the joined path **then**
  prefix-check against the allowed root. `os.path.join` does not stop
  `../`; canonicalisation does.
- Prefix-check against the root plus a trailing separator, or use a
  path-relative API (`path.relative`, `Path.is_relative_to`). A bare
  `resolved.startsWith("/srv/up")` accepts `/srv/uploads-evil`.
- Reject paths containing `..`, NULs, absolute paths, drive letters, UNC
  prefixes, URL-encoded variants (`%2e%2e%2f`).
- On Windows, also reject reserved device names (`CON`, `PRN`, `AUX`,
  `NUL`, `COM1`, `LPT1`...).
- Symlink trap: a chrooted directory can still escape via symlinks created
  by an earlier upload. Either resolve symlinks before trust check, or
  refuse to extract symlinks from archives.

## ZIP slip and archive extraction

- Iterate entries; for each, **canonicalise the destination path then
  prefix-check** against the extraction root.
- Reject entries with absolute paths, `..` segments, or symlinks.
- Cap entry count and total uncompressed size before extraction (zip-bomb
  defence).
- Cap compression ratio per entry (e.g. refuse > 100× ratio without
  explicit allowlist).
- Tar: same rules, plus reject device files and non-regular entries.

## XML / XXE

- Disable external entity resolution at the parser. Defaults vary by
  parser and version (Java JAXP still resolves external entities by
  default), so set the safe configuration explicitly:
  - Java: `XMLConstants.FEATURE_SECURE_PROCESSING = true`,
    `disallow-doctype-decl = true`, set
    `ACCESS_EXTERNAL_DTD/SCHEMA = ""`.
  - Python `lxml`: `etree.XMLParser(resolve_entities=False, no_network=True)`.
    lxml 5.0+ defaults to `resolve_entities='internal'`; older versions
    expand external entities. The stdlib `xml` modules do not fetch
    external entities but still expand internal ones, so use `defusedxml`
    for untrusted input.
  - .NET: `XmlReaderSettings { DtdProcessing = Prohibit, XmlResolver = null }`.
    These are the defaults from .NET Framework 4.5.2 on; set them
    explicitly for older targets.
  - Go: `encoding/xml` does not resolve external entities by default; safe.
- SOAP, SAML, RSS, OOXML, SVG, EPUB are all XML-based and inherit XXE risk.
- XInclude, XSLT, schemaLocation can also fetch URLs; disable.

## Deserialisation

Never deserialise untrusted input via:

- Python `pickle`, `marshal`, `shelve`, `dill`.
- Java `ObjectInputStream` (use a vetted alternative: JSON, protobuf; if
  unavoidable, use look-ahead deserialisation with a strict allowlist).
- PHP `unserialize`.
- Ruby `Marshal.load`, `YAML.unsafe_load`, and `YAML.load` before Psych 4
  (Ruby < 3.1). Psych 4 made `YAML.load` safe; `YAML.safe_load` is safe
  on every version.
- Node `vm.runInNewContext`, `vm.runInThisContext`, `eval`, `Function`.
- .NET `BinaryFormatter` (throws from .NET 9 on unless the unsupported
  compatibility package is added; still live on .NET Framework), `NetDataContractSerializer`,
  `SoapFormatter`, `ObjectStateFormatter`. Even `JavaScriptSerializer` with
  `SimpleTypeResolver` is unsafe.
- Go: most JSON/protobuf use is safe; avoid `gob` for untrusted input.

Use schema-validating JSON / protobuf / Avro instead. Validate with a
generated parser or mature schema library, not hand-rolled type-checks.

## Mass assignment / over-binding

The "framework binds the request body to the entity" pattern. Top OWASP API
risk.

- Bind to a DTO with an explicit allowlist of fields, not directly to the
  ORM entity. The DTO is the authority on what is bindable.
- Strong-parameters / `permit` / class-validator decorators per field.
- Block fields like `is_admin`, `role`, `tenant_id`, `owner_id`, `id`,
  `created_at`, `password_hash`: the field types that should never be
  client-controlled.
- For JSON Merge Patch / nested updates, validate at every level; nested
  resources are a common bypass.
- Tests: caller submits `{"is_admin": true}` to a normal-user endpoint;
  assert it is rejected (or silently dropped, with a log).

## Regex DoS (ReDoS)

- Never compile a user-supplied regex.
- Audit regexes in hot paths for catastrophic backtracking: patterns with
  nested quantifiers (`(a+)+`), alternations sharing a prefix
  (`(a|a)+`), unbounded `.*` near alternations.
- Prefer linear-time engines: Go `regexp`, Rust `regex`, RE2. For
  backtracking engines, use what the platform offers: .NET has a per-match
  timeout (`matchTimeout`) and `RegexOptions.NonBacktracking` (.NET 7+);
  PCRE has match and backtrack limits. JS and Java have no built-in regex
  timeout: use an RE2 binding or run the match where it can be killed.
- Cap input length before matching.

## Other parser traps

- HTTP request smuggling / parser differentials. If you sit behind a
  CDN / load balancer / app server pair, ensure both agree on
  `Transfer-Encoding` vs `Content-Length`. Misalignment lets an attacker
  smuggle a second request through the front-end.
- CRLF / header injection. User input interpolated into `Set-Cookie`,
  `Location`, custom headers must be CRLF-stripped (or rejected). Most
  framework cookie/header APIs do this; only the unsafe ones (writing
  raw bytes) are exposed.
- JSON / YAML parser quirks. YAML `!!python/object` and similar tag
  systems are deserialisation, not parsing; covered above. JSON: duplicate
  keys are parser-defined; pick a parser that rejects them or document the
  rule.

## Prototype pollution

User-controlled JSON merged into an object via deep-clone, deep-merge,
or recursive copy can mutate `Object.prototype` if the merger walks the
prototype chain. Many hand-rolled guards are illusory: for example, a
`getPrototypeOf` check before `clone[key] = …` still walks the chain
and lets `__proto__` keys land on the target. Once `Object.prototype`
gains an attacker-controlled property (`isAdmin`, `polluted`, etc.),
every plain object in the runtime inherits it.

Write the negative test first: feed an input like
`{"__proto__": {"polluted": 1}}` (and the equivalent
`{"constructor": {"prototype": {"polluted": 1}}}`) through your merger
and assert `Object.prototype.polluted` is `undefined` afterwards. If
the test passes without your guard, the guard isn't doing anything; if
the test can't be written, the guard is illusory.

Prefer the structural fix over a guard:

- `Object.create(null)` maps for untrusted key/value containers: no
  prototype to pollute.
- `Map` or `Set` instead of plain objects when keys are arbitrary.
- Maintained merge libraries with current advisories checked rather
  than hand-rolled recursion.

If a guard is genuinely required, deny the dangerous keys at the parse
boundary (`__proto__`, `prototype`, `constructor`) and ship the
negative test alongside it.
