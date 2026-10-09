# Dependency audit

Reference for the `security` skill. Detect known-vulnerable dependencies. Pick
the auditor by lockfile sentinel; treat any non-zero exit as findings to
triage.

## Run order

1. Detect the lockfile in the repo.
2. Run the matching auditor below.
3. For each finding, list package, installed version, fixed version, advisory
   ID, severity, and whether the vulnerable code path is reachable from
   shipped code.
4. Block merge on any unresolved finding ≥ high severity that reaches a
   shipped code path. Document explicit risk acceptance for findings you
   choose not to fix now.

## Per-ecosystem commands

| Lockfile | Command | Notes |
|---|---|---|
| `pnpm-lock.yaml` | `pnpm audit --prod` | Add `--audit-level=high` to threshold in CI. |
| `package-lock.json`, `npm-shrinkwrap.json` | `npm audit --omit=dev` | npm 7+. |
| `yarn.lock` (Berry, v2+) | `yarn npm audit --recursive --environment production` | Detect via `yarn --version` ≥ 2. |
| `yarn.lock` (Classic, v1) | `yarn audit --groups dependencies` | v1 has no `yarn npm` subcommand. |
| `bun.lock`, `bun.lockb` | `bun audit` | Bun ≥ 1.2.15. |
| `requirements*.txt` | `uv run pip-audit -r requirements.txt --strict` | Requires `pip-audit` pinned in the project. If not, use `uv tool run pip-audit==<pinned-version> ...`. |
| `pyproject.toml`, `pylock.*.toml` | `uv run pip-audit --locked . --strict` | `pip-audit --locked` currently supports Python project files, not every ecosystem lockfile. |
| `uv.lock`, `poetry.lock`, `Pipfile.lock`, `pdm.lock` | `osv-scanner scan source -r .` | OSV Scanner supports these lockfiles. If policy requires `pip-audit`, export exact pinned requirements first and audit that artifact. |
| `Cargo.lock` | `cargo audit` | Install with `cargo install cargo-audit`. |
| `Gemfile.lock` | `bundle exec bundler-audit check --update` | `--update` refreshes the advisory DB. |
| `go.mod`, `go.sum` | `govulncheck ./...` | Reachability-aware: only flags advisories whose code is called. |
| `composer.lock` | `composer audit` | Composer ≥ 2.4. |
| `mix.lock` | `mix deps.audit` | Requires the `:mix_audit` dep. |
| `*.csproj`, `packages.lock.json` | `dotnet list package --vulnerable --include-transitive` | Needs `<RestorePackagesWithLockFile>true` for transitives. .NET 8 SDK+ also audits on `restore` (`NuGetAudit`); set `NuGetAuditMode=all` below `net10.0` to include transitives. |
| `pom.xml` | `mvn org.owasp:dependency-check-maven:check` | Slow; cache the NVD mirror. |
| `build.gradle*` | `gradle dependencyCheckAnalyze` | Apply the OWASP dependency-check plugin. |
| `Package.resolved` (Swift PM) | No native local auditor | Use platform dependency review or vendor SCA that explicitly supports Swift PM. `swift package show-dependencies --format json` proves the resolved graph only; it is not a vulnerability audit. |

## Multi-language fallback

`osv-scanner scan source -r .` reads every supported lockfile in the tree and
queries OSV.dev. Use it in monorepos and as a coverage check against the
per-ecosystem tool.

## Container / image scan

Source-tree audit does not cover OS packages baked into the runtime image:

- `trivy image <ref>`: fast, broad, includes OS + language deps.
- `grype <ref>`: alternative engine; useful for cross-checking.
- `docker scout cves <ref>`: Docker Hub native.

Run on the image about to be promoted, not on the source tree alone.

## What audit does not cover

- Logic vulnerabilities in your own code.
- Backdoored or typosquatted packages with no CVE yet. See the `infra.md`
  notes on dependency confusion and disabling install scripts.
- Build-time supply-chain compromise. Use SLSA provenance attestations.
- Transitive deps pulled at install time outside the lockfile. Avoid by
  pinning and using `--frozen-lockfile`, `--locked`, `npm ci` in CI.
- Vulnerabilities in tools used at build time but not shipped (still relevant
  if they touch secrets).
