# Secrets, tokens, passwords, MFA, sessions

Reference for the `security` skill. How secrets move, how tokens are picked,
how credentials are stored, how sessions are managed. Pair with
`secrets-scan.md` for detecting leaks of anything stored here, and
`api-and-auth.md` for OAuth / OIDC implementation pitfalls.

## Secrets architecture

### Where secrets must not live

- Source code or version control.
- Environment variable files committed to repos (`.env`,
  `config/production.yml`).
- Application logs, audit trails, or trace spans.
- Client-side code or mobile apps (the binary can be unpacked).

### Where secrets belong

- Development: `.env` files in `.gitignore`, loaded via `direnv` or equivalent.
- CI/CD: platform secret stores (GitHub Actions secrets, GitLab CI variables,
  AWS Secrets Manager, Vault).
- Production: workload identity where possible: IRSA on EKS, Workload Identity
  on GKE, SPIFFE/SPIRE for non-cloud. No static credential to rotate, no
  credential to leak.

### Envelope encryption

Encrypt data with a data encryption key (DEK); encrypt the DEK with a key
encryption key (KEK) managed by KMS. The plaintext DEK is never stored:
only the encrypted envelope. Rotate KEKs regularly; re-wrapping DEKs does
not require re-encrypting the underlying data.

### Rotation

Tie the rotation cadence to the credential type and blast radius, not a
fixed clock, but **make rotation a non-event** so any rotation is cheap
when needed. If rotating is a crisis, the system is coupled to a specific
credential instance.

| Credential | Typical lifetime |
|---|---|
| Workload-identity / OIDC-issued tokens | minutes |
| Short-lived service certs (Vault PKI, SPIRE) | ≤ 24 h |
| User session tokens | hours to days |
| Static API keys for partners | ≤ 1 year, with overlap window for rotation |
| KMS data-encryption keys | re-wrap as needed; rotate KEK on policy |
| SSH host keys | years (don't churn for the sake of churn) |

Automate. Treat manually-rotated keys as drift.

## Auth tokens: pin the algorithm, choose the format

The actual safety win is **pinning the algorithm from trusted configuration,
never the token header**. Both formats below get this right when used
correctly; both have shipped insecure deployments when used carelessly.

JWT has a long history of algorithm-confusion CVEs (`alg: none`, RS256 →
HS256 confusion, header injection, weak key validation). The bugs come from
trusting the token's own `alg` field. PASETO (Platform-Agnostic Security
Tokens) sidesteps this by encoding the algorithm in the token version, with
no `alg` field at all.

### When PASETO is a fit

New code, full control of issuer and verifier, mature library available in
your language, no requirement to interoperate with a hosted IDP. Use
`v4.local` for symmetric (issuer = verifier), `v4.public` for asymmetric
(cross trust boundary).

### When JWT is fine (and unavoidable)

Any hosted identity provider (Auth0, Okta, Cognito, Clerk, WorkOS, Entra)
emits JWTs; OIDC, SAML companion flows, federated SSO. The format is fine
if you validate it correctly. See `api-and-auth.md` for the full validation
checklist (JWKS pinning, `kid` handling, `alg` allowlist, `iss`/`aud`/`exp`/`nbf`
checks, `nonce` for OIDC).

### Common rules either way

- **Pin the allowed algorithm set in trusted configuration** (OIDC
  metadata, JWKS, server config). Reject anything else, including
  `alg: none`. Reject tokens whose key type does not match the algorithm.
- Short expiry (≤ 15 min for access tokens) + refresh tokens with rotation.
- Never put sensitive data in the payload: JWT is base64-encoded, PASETO
  `*.public` is signed but not encrypted.

OAuth2 + OIDC for federated identity. Never roll your own auth protocol;
use the platform's maintained provider SDK or OIDC client library. See
`api-and-auth.md` for client and server pitfalls (PKCE, `state`, `nonce`,
`redirect_uri` exact match, refresh-token rotation, audience binding).

## Passwords

NIST SP 800-63B-4 is the baseline; this list applies (and tightens)
those rules.

- Min length ≥ 15 for single-factor passwords. If the password is only
  one factor in MFA, ≥ 8 is the NIST minimum. Max ≥ 64. Allow all
  printable Unicode including spaces.
- **Allow paste.** Password managers depend on it. Same for show-password
  toggles.
- No composition rules (no forced uppercase / number / special).
- No forced periodic rotation. Only require change on compromise signal
  (breached-password match, account takeover indicators, admin reset).
- No knowledge-based recovery questions ("mother's maiden name").
- No password hints stored or rendered.
- Check candidates against a breached-password list on set/change. The
  HaveIBeenPwned k-anonymity API is free and never receives the full
  password.
- Store with a maintained password-hashing library using a memory-hard
  KDF. Current OWASP guidance:
  - argon2id (preferred): `m = 19 MiB, t = 2, p = 1` minimum, or
    `m = 46 MiB, t = 1, p = 1`. Tune to ~250–500 ms per hash on
    production hardware.
  - scrypt: `N = 2^17, r = 8, p = 1` minimum.
  - bcrypt: OWASP minimum cost is ≥ 10; Consult prefers ≥ 12 when the
    measured login latency budget allows it. Bcrypt truncates at 72
    bytes in most implementations, so prefer argon2id / scrypt for new
    systems. If forced to pre-hash for bcrypt compatibility, use a
    library-documented HMAC/pepper scheme rather than raw SHA-256.
- Apply per-account rate limits and a global failed-login rate limit;
  alert on spikes. See `api-and-auth.md` for the rate-limit pattern.
- Account recovery / password-reset tokens: ≥ 128 bits CSPRNG,
  single-use, ≤ 15 min validity, bound to account ID. Send via the
  user's verified channel (email or in-app notification). An emailed
  link must carry the token, and URLs leak via logs, browser history,
  and `Referer`. So serve the landing page with
  `Referrer-Policy: no-referrer`, move the token into form state or a
  short-lived cookie on landing, and redirect to a URL without it.
  Consume the token only on the POST that sets the new password,
  because email link scanners fetch the GET before the user does. Avoid
  fragments too unless the flow is deliberately client-side; fragments
  are readable by same-origin JavaScript and do not reach the server.
  Rotate the session ID on successful reset.

## MFA

- Require a phishing-resistant factor (WebAuthn / passkeys, FIDO2) for any
  admin or privileged role.
- SMS OTP is a fallback only, never the sole factor.
- TOTP (authenticator app) is acceptable for general users; prefer
  WebAuthn / passkeys where available.
- Enrollment flows: enforce MFA before step-up to any privileged action,
  not only at login.

### Backup codes

Generate 8–10 single-use codes on enrolment; render once and require user
acknowledgement. Store hashed at rest (SHA-256 is fine, high-entropy
secret). Mark each code consumed on use; allow regeneration which
invalidates the previous set. Treat backup-code use as a security event
(audit log + user notification).

### WebAuthn server validation gotchas

- Validate the `clientDataJSON.origin` against your expected origin
  exactly. Mismatches are spoofing attempts.
- Validate `rpIdHash` against your configured Relying Party ID; do not
  derive it from the request.
- Check the `userVerification` flag against your policy (`required` for
  privileged operations).
- Enforce `signCount` monotonicity per credential; a regression suggests
  cloned authenticator (rare with hardware, possible with software
  passkeys synced across devices; pick a policy and document it).
- Validate attestation only when you actually use the result. Most apps
  do not need attestation; pick `attestation: "none"` and skip the parse.

## Sessions

- **Rotate session ID on every privilege change**, not only on login. Step-up
  MFA, role change, password change, account unlock, email change all
  rotate. This blocks session-fixation attacks where an attacker plants a
  known session ID before the user authenticates.
- Short idle timeout for privileged sessions (≤ 15 min). Absolute maximum
  lifetime ≤ 24 h for sensitive sessions; longer is fine for low-stakes
  consumer apps with re-auth on sensitive actions.
- Session cookies: `HttpOnly`, `Secure`, `SameSite=Lax` (or `Strict` for
  admin), `Path` scoped. Use the `__Host-` prefix on session cookies to
  pin them to the exact origin (`Path=/`, `Secure`, no `Domain` attribute).
  See `web-app.md`.
- Revocation: maintain a session registry and honour server-side
  logout / revoke across all devices. "Sign out everywhere" is a feature
  users expect and incidents require.
- Do not reuse session IDs as authorisation tokens for cross-service
  calls: use a separate short-lived service token (see service identity
  below).

## Service identity

Service-to-service calls use mTLS; both sides present and verify
certificates.

- Prefer SPIFFE/SPIRE-issued SVIDs (X.509 or JWT SVIDs, auto-rotated).
- Or a service mesh (Istio, Linkerd) that handles SVID distribution and
  rotation.
- Without a mesh, use Vault PKI for short-lived (≤ 24h) per-service certs
  with automatic renewal.
- Never embed long-lived service credentials in container images or env
  vars.

## CI / build identity

The modern way to remove static credentials from CI:

- Workload-identity federation: GitHub Actions OIDC → AWS / GCP / Azure;
  GitLab JWT → cloud roles; Buildkite OIDC. The CI system mints a
  short-lived token at job time, the cloud trusts the issuer, no static
  key changes hands.
- Scope cloud roles per-repo and per-environment (production gated on
  branch / environment protection rules).
- Where federation is not supported, store credentials in the platform
  secret store (GitHub Actions secrets, AWS Secrets Manager) with
  environment scoping; never commit them.
- See `infra.md` for the broader CI / supply-chain controls (pinned
  Action SHAs, `pull_request_target` hazards, signed artifacts).
