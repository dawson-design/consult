#!/usr/bin/env bash
# Refresh installed Consult plugins through each agent's official install path.
set -euo pipefail

REPO_ROOT=$(cd "$(dirname "$0")/.." && pwd)
DRY_RUN=0
FAILED=0

usage() {
	cat <<EOF
Usage: scripts/update-installed-plugins.sh [--dry-run]

Update installed Consult plugins through official installer paths exposed by
each agent harness. This script does not copy skills or plugin files into agent
cache directories.

Options:
  --dry-run  Print commands without executing them.
  -h, --help Show this help.
EOF
}

while [ "$#" -gt 0 ]; do
	case "$1" in
	--dry-run)
		DRY_RUN=1
		;;
	-h | --help)
		usage
		exit 0
		;;
	*)
		echo "ERROR: unknown option: $1" >&2
		usage >&2
		exit 2
		;;
	esac
	shift
done

print_command() {
	printf "  "
	printf "%q " "$@"
	printf "\n"
}

run_if_available() {
	local label="$1"
	local command_name="$2"
	shift 2

	if ! command -v "$command_name" >/dev/null 2>&1; then
		echo "$label: $command_name not found; skipping."
		return
	fi

	echo "$label:"
	print_command "$@"
	if [ "$DRY_RUN" -eq 1 ]; then
		return
	fi

	if "$@"; then
		echo "$label: updated."
	else
		echo "$label: update failed." >&2
		FAILED=1
	fi
}

run_best_effort_if_available() {
	local label="$1"
	local command_name="$2"
	shift 2

	if ! command -v "$command_name" >/dev/null 2>&1; then
		echo "$label: $command_name not found; skipping."
		return
	fi

	echo "$label:"
	print_command "$@"
	if [ "$DRY_RUN" -eq 1 ]; then
		return
	fi

	if "$@"; then
		echo "$label: completed."
	else
		echo "$label: skipped or already configured."
	fi
}

run_headless_if_available() {
	local label="$1"
	local command_name="$2"
	local prompt="$3"
	shift 3

	if ! command -v "$command_name" >/dev/null 2>&1; then
		echo "$label: $command_name not found; skipping."
		return
	fi

	echo "$label:"
	print_command "$@" "$prompt"
	if [ "$DRY_RUN" -eq 1 ]; then
		return
	fi

	if "$@" "$prompt"; then
		echo "$label: update prompt completed."
	else
		echo "$label: update prompt failed." >&2
		FAILED=1
	fi
}

cat <<EOF
Consult plugin refresh

CLI-backed official update paths will run when their CLIs are installed.
This script does not copy skills or plugin files into cache directories.
EOF

echo ""
run_best_effort_if_available "Claude Code marketplace" claude claude plugin marketplace add dawson-design/consult
run_if_available "Claude Code marketplace" claude claude plugin marketplace update consult
run_best_effort_if_available "Claude Code plugin" claude claude plugin install consult@consult
run_if_available "Claude Code plugin" claude claude plugin update consult@consult
echo "Claude Code: restart Claude Code if prompted so the updated plugin is loaded."

echo ""
run_best_effort_if_available "Codex marketplace" codex codex plugin marketplace add dawson-design/consult
run_if_available "Codex" codex codex plugin marketplace upgrade consult
run_if_available "Codex" codex codex plugin add consult@consult

echo ""
run_if_available "Google Antigravity" agy agy plugin install "$REPO_ROOT/plugin"
echo "Google Antigravity: verify with 'agy plugin list'."

echo ""
run_headless_if_available \
	"Cursor Agent" \
	cursor \
	"Update the Consult plugin from the Cursor Marketplace using Cursor's official plugin-management path. Do not copy files into plugin directories manually. If this harness cannot update marketplace plugins headlessly, report that limitation and the official Cursor Marketplace action the user must take." \
	cursor agent --print

cat <<EOF

Cursor: if the harness reports that marketplace plugin updates are not available
headlessly, update Consult from the Cursor Marketplace in Cursor and reload the
window.
EOF

exit "$FAILED"
