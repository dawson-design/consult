SHELL := /bin/bash
.SHELLFLAGS := -euo pipefail -c

.PHONY: check test lint format typecheck validate plugin eval eval-fast eval-triggers

# Everything that must pass before a commit.
check: validate lint typecheck test

# Skill anatomy and size caps, then drift between sources and plugin/.
validate:
	python3 scripts/validate_skills.py
	python3 scripts/build_plugin.py --check

# Regenerate plugin/skills and plugin/hooks/hooks.json from agents/.agents/.
plugin:
	python3 scripts/build_plugin.py

test:
	uv run --locked pytest -q

lint:
	uv run --locked ruff check
	uv run --locked ruff format --check

format:
	uv run --locked ruff format

typecheck:
	uv run --locked mypy

# Harbor evals; need Docker, harbor, and CLAUDE_CODE_OAUTH_TOKEN. See eval/README.md.
eval:
	uv run --project eval eval/scripts/sync_tests.py --check
	npm ci --prefix eval/verifier/analyzer --no-audit --no-fund --silent
	uv run --project eval python -m unittest discover eval/verifier/tests

eval-fast:
	uv run --project eval eval/scripts/run.py --tier fast $(ARGS)

eval-triggers:
	uv run --project eval eval/scripts/triggers.py $(ARGS)
