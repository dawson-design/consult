# SSRF and outbound egress

Reference for the `security` skill. The patterns and mitigations for
server-side request forgery and any feature that fetches a URL on behalf of a
user.

## When this applies

- Webhook senders, image proxies, link-preview / OG-tag fetchers, RSS readers,
  OAuth callback fetchers, file-import-from-URL, server-rendered iframe-style
  features, integrations that callback to user-supplied endpoints.
- Any agent or LLM tool that accepts a URL and fetches it.

## Threat model

A user (or a chained external attacker via a stored URL) controls the
destination of an outbound HTTP request from your server. The server has
network access the attacker does not: internal services, cloud metadata,
neighbouring tenants, intranet admin panels, databases on private IPs.

## Iron rules

1. Never fetch a URL straight from user input. Always run it through a
   validator first.
2. Validate the **resolved IP**, not the hostname. Hostname allowlists alone
   are bypassed by DNS rebinding.
3. Pin the IP between resolution and connect; do not let the resolver run a
   second time inside the HTTP client.
4. Fail closed. If validation cannot decide, refuse the fetch.

## Block list (deny these resolved IPs)

IPv4: `0.0.0.0/8`, `10.0.0.0/8`, `100.64.0.0/10` (CGNAT), `127.0.0.0/8`,
`169.254.0.0/16` (link-local; cloud metadata), `172.16.0.0/12`, `192.0.0.0/24`,
`192.168.0.0/16`, `198.18.0.0/15`, `224.0.0.0/4` (multicast), `240.0.0.0/4`
(reserved).

IPv6: `::/128`, `::1/128`, `fc00::/7` (ULA), `fe80::/10` (link-local),
`ff00::/8` (multicast), `64:ff9b::/96` (NAT64), `2001:db8::/32` (doc), and
IPv4-mapped (`::ffff:0:0/96`) targeting any blocked v4.

Cloud metadata endpoints to deny by default: `169.254.169.254` (AWS, GCP,
Azure, OpenStack, DigitalOcean), `fd00:ec2::254` (AWS IMDS over IPv6),
`metadata.google.internal`, `100.100.100.200` (Alibaba), `169.254.170.2` (AWS
task metadata).

## Allowlist (preferred over blocklist)

If the feature has a known set of destinations (e.g. only fetches images from
a list of CDNs), allowlist them and reject everything else. Allowlist by
**registered domain** (eTLD+1 via the public suffix list), not raw hostname; a
naive wildcard subdomain rule lets `attacker.example.com` past the gate.

## DNS rebinding mitigation

1. Resolve the hostname once.
2. Validate every returned A/AAAA against the block/allow list. If any address
   is blocked, refuse.
3. Connect to the resolved IP, not by re-resolving the hostname inside the
   HTTP client.
4. Keep the original hostname for TLS: send it as SNI and verify the
   certificate against it, and send it as the `Host` header. Connecting
   by IP must not skip hostname verification.

## HTTP client hardening

- Disable redirects by default; if redirects are required, validate every
  hop's target against the same rules.
- Cap response size and read time before any application logic runs.
- Strip credentials from URLs (`https://user:pass@host/`).
- Disable URL schemes other than `http`/`https`. `file://`, `gopher://`,
  `dict://`, `ftp://`, `jar://`, `php://` and friends are SSRF amplifiers.
- Send no ambient credentials (no cookies, no proxy auth, no instance
  metadata) on the outbound fetch.
- Java/Spring caveat: `URL.openConnection()` follows redirects and supports
  `file://` by default. Wrap in a hardened client.
- Node `fetch`/`undici` and Go `http.DefaultClient` follow redirects by
  default. Configure explicitly.

## Cloud metadata defence in depth

- AWS: enforce IMDSv2 (`HttpTokens: required`); set
  `HttpPutResponseHopLimit: 1` so containers cannot reach IMDS through the
  host.
- GCP: the metadata server rejects requests without
  `Metadata-Flavor: Google` and any request carrying `X-Forwarded-For`.
  That blocks naive
  URL-only SSRF and requests relayed through a standard proxy. It does not
  stop an SSRF primitive that lets the attacker set request headers.
- Use workload identity (IRSA on EKS, Workload Identity on GKE, federated
  OIDC for CI) so a leaked metadata response is not, by itself, a long-lived
  credential.

## Egress controls outside the app

- Run the fetcher in a network namespace that can only reach the public
  internet, not the VPC.
- Use a forward proxy with its own allowlist and audit log; force outbound
  HTTP through it.
- Egress NACLs / security groups: block the metadata IP at the subnet level
  for workloads that have no business calling it.

## Tests

- Unit: every entry in the block list returns "refused."
- Unit: hostname that resolves to a blocked IP is refused.
- Unit: redirect to a blocked IP is refused.
- Integration: fetch of `http://169.254.169.254/latest/meta-data/` returns
  refused with no upstream call.
- Integration: a DNS server that returns a public IP on the first query and
  `127.0.0.1` on the second cannot rebind.
