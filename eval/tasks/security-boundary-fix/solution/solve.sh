#!/bin/bash
# Oracle: an allowlist redirect check. A target is resolved the way a browser
# would resolve it from the app, with the platform URL parser, and kept only
# when it lands on the one trusted HTTPS origin. Everything else, including
# parse failures and non-strings, falls back to "/". The request names no
# host, so the trusted origin is a placeholder the report must flag.
set -euo pipefail
cd /app
cat > src/redirect.js <<'JS'
// The only origin redirects may lead to. The request named no host, so this
// is a placeholder for the app's real HTTPS host.
const TRUSTED_ORIGIN = "https://app.example.com";
const FALLBACK = "/";

// Resolves the target against the app, as a browser would. Returns null when
// the target cannot be parsed, so the caller falls back.
function resolveFromApp(target) {
  try {
    return new URL(target, TRUSTED_ORIGIN);
  } catch {
    return null;
  }
}

function isAbsoluteUrl(target) {
  return URL.canParse(target);
}

// Returns the target when it stays on the trusted HTTPS origin: a same-site
// path, or an absolute https URL on the trusted host. Anything else, such as
// another host, another scheme, `//host`, `/\host`, or an unparseable value,
// returns "/".
export function resolveRedirect(target) {
  if (typeof target !== "string" || target === "") return FALLBACK;
  const url = resolveFromApp(target);
  const staysOnTrustedOrigin = url !== null && url.origin === TRUSTED_ORIGIN;
  if (!staysOnTrustedOrigin) return FALLBACK;
  return isAbsoluteUrl(target) ? url.href : url.pathname + url.search + url.hash;
}
JS
cat >> test/redirect.test.js <<'JS'

test("keeps same-site paths, with their query and fragment", () => {
  assert.equal(resolveRedirect("/account/settings"), "/account/settings");
  assert.equal(resolveRedirect("/search?q=shoes#results"), "/search?q=shoes#results");
});

test("accepts an absolute HTTPS URL on the trusted app host", () => {
  assert.equal(resolveRedirect("https://app.example.com/billing?tab=invoices"), "https://app.example.com/billing?tab=invoices");
});

test("falls back for an absolute URL on another host", () => {
  assert.equal(resolveRedirect("https://evil.example/phish"), "/");
});

test("falls back for protocol-relative and backslash targets", () => {
  assert.equal(resolveRedirect("//evil.example/phish"), "/");
  assert.equal(resolveRedirect("/\\evil.example/phish"), "/");
  assert.equal(resolveRedirect("/\t/evil.example/phish"), "/");
});

test("falls back for schemes other than https", () => {
  assert.equal(resolveRedirect("http://app.example.com/billing"), "/");
  assert.equal(resolveRedirect("javascript:alert(1)"), "/");
  assert.equal(resolveRedirect("data:text/html,<script>alert(1)</script>"), "/");
});

test("falls back for hosts that only look like the trusted host", () => {
  assert.equal(resolveRedirect("https://app.example.com.evil.example/x"), "/");
  assert.equal(resolveRedirect("https://evilapp.example.com/x"), "/");
  assert.equal(resolveRedirect("https://app.example.com@evil.example/x"), "/");
  assert.equal(resolveRedirect("https://app.example.com:8443/x"), "/");
});

test("falls back for malformed and non-string targets", () => {
  assert.equal(resolveRedirect("https://"), "/");
  assert.equal(resolveRedirect("http://["), "/");
  assert.equal(resolveRedirect(42), "/");
  assert.equal(resolveRedirect({ toString: () => "/account" }), "/");
});
JS
