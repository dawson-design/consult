# Secrets scanning

Reference for the `security` skill. Detect credentials in source, history,
and the working tree. Run before every commit on sensitive branches and in CI
on every PR.

## Tools

- `gitleaks`: fast, low false-positive rate, regex + entropy + allowlist.
  Default choice.
- `trufflehog`: slower but verifies detected secrets against the live API
  to drop false positives. Use for high-signal triage on hits.
- `git-secrets`: AWS-focused; useful as a cheap pre-commit hook.

## Scopes

| Goal | Command |
|---|---|
| Working tree only | `gitleaks dir . --redact -v` |
| All history | `gitleaks git . --redact -v` |
| Staged diff (pre-commit) | `gitleaks git --pre-commit --staged . --redact -v` |
| Branch since base | `trufflehog git file://. --since-commit <base-commit> --results=verified` |
| Specific commit range | `gitleaks git . --log-opts="<base>..HEAD" --redact -v` |

## CI integration

- Run `gitleaks` on every PR. Block merge on any new finding (compare against
  base).
- Pin the tool version; cache the rules file.
- Do **not** print raw matches in CI logs. `--redact` is mandatory. Logs are
  themselves a secret-leak surface.

## Pre-commit hook

Add to `.pre-commit-config.yaml`:

```yaml
repos:
  - repo: https://github.com/gitleaks/gitleaks
    rev: <commit-sha>  # frozen: v8.x.y
    hooks: [{id: gitleaks}]
```

Pin `rev` to a commit SHA, not a tag or `main`: tags can be moved.
`pre-commit autoupdate --freeze` writes the SHA with a `# frozen:` tag
comment. Review rev changes; pre-commit hooks run with full filesystem
access.

## On a hit

Order matters:

1. **Rotate the credential first.** Treat it as compromised the moment it
   appears in any non-private location: Git history, a CI log, a screenshot,
   a Slack message.
2. Revoke any sessions or derived tokens.
3. Audit usage logs for the credential between commit time and rotation
   time.
4. Then scrub. Use `git filter-repo`; `git filter-branch` is deprecated
   and bug-prone. Force-push, notify collaborators, and accept that any
   clone made before the scrub still contains the secret.
5. Add an allowlist entry only if the match is a true false positive (test
   fixture, public sample). Document why in the allowlist file.

## False-positive triage

- High-entropy strings that are not secrets: UUIDs, hashes, base64 of known
  public data. Allowlist by file path or by exact string.
- Test fixtures with deliberately invalid credentials. Use the documented
  example prefixes the cloud vendor publishes (`AKIAIOSFODNN7EXAMPLE` for
  AWS, etc.) so scanners recognise them.

## Coverage limits

Scanners catch known patterns and high-entropy strings. They miss:

- Custom internal tokens with no recognisable shape. Add a regex to
  `.gitleaks.toml`.
- Secrets concatenated from parts at runtime.
- Secrets in binary blobs, images, PDFs, JSON-stringified inside other JSON.
- Secrets in CI variables / deploy configs / secret managers; those need
  their own audit (rotation cadence, scope, who can read).

## Coordinated with the `secrets.md` reference

Where secrets *belong* (vaults, workload identity, envelope encryption) is
covered in `secrets.md`. This file is only about detecting leaks of secrets
that escaped the controls in `secrets.md`.
