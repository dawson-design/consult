SHELL := /bin/bash
.SHELLFLAGS := -euo pipefail -c

.PHONY: test lint links eval eval-fast eval-triggers smoke update-installed-plugins update-installed-plugins-dry-run

# Cheap, deterministic checks first: a failing test suite must not stop the
# validator from reporting, since prose changes are the common case and the
# validator is the check that covers them.
test:
	python3 scripts/validate_skill_anatomy.py
	python3 scripts/validate_skill_anatomy.py --self-test
	$(MAKE) --no-print-directory lint
	$(MAKE) --no-print-directory links
	python3 -m unittest discover -s tests

# Lint and format checks for every repo-owned Python file, using the ruff
# version pinned in the root pyproject.toml. `uv run ruff format` fixes the
# formatting findings.
lint:
	uv run --locked ruff check
	uv run --locked ruff format --check

# Local links and heading anchors in every tracked Markdown file. --offline
# skips remote URLs, so the check is deterministic and makes no network
# calls. Install lychee with `brew install lychee`.
links:
	git ls-files -z -- '*.md' | xargs -0 lychee --offline --include-fragments --no-progress

# Static checks for the Harbor eval suite: the vendored verifier copies match
# their source, the rule checks pass their fixtures, and the smoke job config
# resolves. Needs `harbor` and `uv` on PATH, so it is opt-in rather than part
# of `make test`.
eval:
	uv run --project eval eval/scripts/sync_tests.py --check
	uv run --project eval python -m unittest discover eval/verifier/tests
	harbor run -c eval/jobs/smoke.example.yaml --dry-run --yes

# Run the smoke suite through Harbor with Consult skills against a real Claude
# Code session. Uses the subscription token (CLAUDE_CODE_OAUTH_TOKEN), so it does
# not bill the API. See eval/README.md for setup and other suites.
smoke:
	uv run --project eval eval/scripts/run.py --suite smoke --agent claude-code --arms consult $(ARGS)

# Fast eval tier: the tasks that exercise the skills changed since HEAD, consult
# arm only, no judge, against the saved release baseline. See eval/README.md.
eval-fast:
	uv run --project eval eval/scripts/run.py --tier fast $(ARGS)

# Trigger suite: does Claude Code load the right Consult skill before its first
# write, and stay silent on trivial edits? Needs Docker and
# CLAUDE_CODE_OAUTH_TOKEN. See eval/README.md.
eval-triggers:
	uv run --project eval eval/scripts/triggers.py $(ARGS)

update-installed-plugins:
	scripts/update-installed-plugins.sh

update-installed-plugins-dry-run:
	scripts/update-installed-plugins.sh --dry-run
