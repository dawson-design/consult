#!/usr/bin/env bash
# One-click local installer for Consult's shared skills and agent compatibility links.
set -euo pipefail

usage() {
	cat <<EOF
Usage: ./setup.sh

Install Consult skills into ~/.agents and wire local agent compatibility links.

Options:
  -h, --help Show this help.
EOF
}

if [ "$#" -gt 0 ]; then
	case "$1" in
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
fi

AGENTS_SKILLS="$HOME/.agents/skills"
REPO_ROOT=$(cd "$(dirname "$0")" && pwd)
STOW_COMMAND=(
	stow
	--target="$HOME"
	--ignore='^AGENTS\.md$'
	--ignore='^\.claude/CLAUDE\.md$'
	agents
)

confirm() {
	local prompt="$1"
	local answer

	if [ ! -t 0 ]; then
		echo "WARNING: non-interactive setup; cannot ask for confirmation."
		return 1
	fi

	printf "%s [y/N] " "$prompt"
	read -r answer
	case "$answer" in
	y | Y | yes | YES | Yes) return 0 ;;
	*) return 1 ;;
	esac
}

require_stow() {
	if command -v stow >/dev/null 2>&1; then
		return
	fi

	cat >&2 <<EOF
ERROR: GNU Stow is required for local Consult installs.

Install it, then rerun ./setup.sh:

  macOS:          brew install stow
  Debian/Ubuntu:  sudo apt install stow
  Fedora:         sudo dnf install stow
EOF
	exit 1
}

run_stow_install() {
	echo ""
	echo "Linking shared skills with GNU Stow..."
	(cd "$REPO_ROOT" && "${STOW_COMMAND[@]}")

	if [ ! -d "$AGENTS_SKILLS" ]; then
		cat >&2 <<EOF
ERROR: Stow finished, but $AGENTS_SKILLS was not created.

Check the Stow output above for conflicts, then rerun ./setup.sh.
EOF
		exit 1
	fi
}

points_into_agents_skills() {
	case "$1" in
	"$AGENTS_SKILLS"/* | "$AGENTS_SKILLS_REAL"/*) return 0 ;;
	*) return 1 ;;
	esac
}

prune_stale_skill_links() {
	local label="$1"
	local target_dir="$2"
	local target link_target

	for target in "$target_dir"/*; do
		[ -e "$target" ] || [ -L "$target" ] || continue
		[ -L "$target" ] || continue

		link_target=$(readlink "$target")
		if points_into_agents_skills "$link_target" && [ ! -e "$target" ]; then
			rm "$target"
			echo "$label: removed stale skill link $(basename "$target")"
		fi
	done
}

backup_path_for() {
	local target="$1"
	local stamp
	stamp=$(date +%Y%m%d%H%M%S)
	printf "%s.has-backup.%s.%s" "$target" "$stamp" "$$"
}

link_skill() {
	local label="$1"
	local target="$2"
	local source="$3"
	ln -s "$source" "$target"
	echo "$label: linked ${target/#$HOME/~} → ${source/#$HOME/~}"
}

replace_symlink_if_confirmed() {
	local label="$1"
	local target="$2"
	local current_target="$3"
	local source="$4"

	echo "WARNING: $target is a symlink to $current_target. Expected $source."
	if confirm "$label: replace it with a symlink to $source?"; then
		rm "$target"
		link_skill "$label" "$target" "$source"
	else
		echo "$label: skipping $(basename "$target")"
	fi
}

replace_directory_if_confirmed() {
	local label="$1"
	local target="$2"
	local source="$3"
	local backup

	echo "WARNING: $target exists as a real directory."
	if confirm "$label: move it to a backup and replace it with a symlink to $source?"; then
		backup=$(backup_path_for "$target")
		mv "$target" "$backup"
		echo "$label: moved ${target/#$HOME/~} → ${backup/#$HOME/~}"
		link_skill "$label" "$target" "$source"
	else
		echo "$label: skipping $(basename "$target")"
	fi
}

replace_file_if_confirmed() {
	local label="$1"
	local target="$2"
	local source="$3"
	local backup

	echo "WARNING: $target exists as a real file."
	if confirm "$label: move it to a backup and replace it with a symlink to $source?"; then
		backup=$(backup_path_for "$target")
		mv "$target" "$backup"
		echo "$label: moved ${target/#$HOME/~} → ${backup/#$HOME/~}"
		link_skill "$label" "$target" "$source"
	else
		echo "$label: skipping $(basename "$target")"
	fi
}

confirm_setup_start() {
	cat <<EOF
Consult setup will:
  - run GNU Stow from this checkout to link shared skills into ~/.agents/skills
  - link ~/.claude/skills to ~/.agents/skills when safe
  - install the Consult plugin with "agy plugin install" when the Google
    Antigravity CLI (agy) is installed
  - link individual Consult skills into ~/.codex/skills when Codex is installed
    without the Consult Codex plugin, or prune those legacy links when the plugin
    is present
  - link individual Consult skills into ~/.codeium/windsurf/skills when Windsurf is installed
  - prune stale Consult-owned skill links and legacy command links
  - ask before replacing conflicting symlinks or moving real directories
  - sync plugin/ skill links when python3 is available

It will not overwrite real skill directories or third-party symlinks without
showing the exact path and asking again.
EOF

	if confirm "Continue with setup?"; then
		return
	fi

	echo "Setup cancelled."
	exit 1
}

require_stow
confirm_setup_start
run_stow_install

AGENTS_SKILLS_REAL=$(cd "$AGENTS_SKILLS" && pwd -P)

# Claude Code: symlink the whole skills dir
CLAUDE_SKILLS="$HOME/.claude/skills"
mkdir -p "$(dirname "$CLAUDE_SKILLS")"
if [ -L "$CLAUDE_SKILLS" ]; then
	claude_target=$(readlink "$CLAUDE_SKILLS")
	if points_into_agents_skills "$claude_target"; then
		echo "${CLAUDE_SKILLS/#$HOME/~} already symlinked, skipping"
	else
		replace_symlink_if_confirmed "Claude Code" "$CLAUDE_SKILLS" "$claude_target" "$AGENTS_SKILLS"
	fi
elif [ -d "$CLAUDE_SKILLS" ]; then
	replace_directory_if_confirmed "Claude Code" "$CLAUDE_SKILLS" "$AGENTS_SKILLS"
else
	link_skill "Claude Code" "$CLAUDE_SKILLS" "$AGENTS_SKILLS"
fi

# Per-agent per-skill symlinks. Per-skill (not whole-dir) preserves any
# marketplace or user-added skills already in each agent's skills directory.
#
# Windsurf is conditional because it stores under ~/.codeium/windsurf/, which
# only exists if Windsurf is installed.
link_skills_per_agent() {
	local label="$1"
	local target_dir="$2"
	if [ ! -d "$(dirname "$target_dir")" ]; then
		echo "$label not installed; skipping (no $(dirname "$target_dir"))"
		return
	fi
	mkdir -p "$target_dir"
	prune_stale_skill_links "$label" "$target_dir"
	for skill_dir in "$AGENTS_SKILLS"/*/; do
		local skill_name
		local expected_target
		local expected_real_target
		local current_target
		skill_name=$(basename "$skill_dir")
		local target="$target_dir/$skill_name"
		expected_target="${skill_dir%/}/"
		expected_real_target="$AGENTS_SKILLS_REAL/$skill_name/"
		if [ -L "$target" ]; then
			current_target=$(readlink "$target")
			if [ "$current_target" = "$expected_target" ] ||
				[ "$current_target" = "${expected_target%/}" ] ||
				[ "$current_target" = "$expected_real_target" ] ||
				[ "$current_target" = "${expected_real_target%/}" ]; then
				echo "$label: $skill_name already symlinked, skipping"
			else
				replace_symlink_if_confirmed "$label" "$target" "$current_target" "$expected_target"
			fi
		elif [ -d "$target" ]; then
			replace_directory_if_confirmed "$label" "$target" "$expected_target"
		else
			link_skill "$label" "$target" "$skill_dir"
		fi
	done
}

configure_antigravity_plugin() {
	if ! command -v agy >/dev/null 2>&1; then
		echo "Google Antigravity (agy) not installed; skipping plugin install"
		echo "(no agy command on PATH)"
		return
	fi

	echo "Google Antigravity: installing Consult plugin via 'agy plugin install'"
	if agy plugin install "$REPO_ROOT/plugin" </dev/null; then
		echo "Google Antigravity: Consult plugin installed (verify with 'agy plugin list')"
	else
		echo "Google Antigravity: 'agy plugin install' failed; install manually with:"
		echo "  agy plugin install $REPO_ROOT/plugin"
	fi
}

remove_consult_skill_links() {
	local label="$1"
	local target_dir="$2"
	if [ ! -d "$target_dir" ]; then
		return
	fi

	for skill_dir in "$AGENTS_SKILLS"/*/; do
		local skill_name
		local target
		local current_target
		skill_name=$(basename "$skill_dir")
		target="$target_dir/$skill_name"

		if [ ! -L "$target" ]; then
			continue
		fi

		current_target=$(readlink "$target")
		if points_into_agents_skills "$current_target"; then
			rm "$target"
			echo "$label: removed manual skill link $skill_name (plugin installed)"
		fi
	done
}

codex_consult_plugin_installed() {
	local manifest
	for manifest in "$HOME"/.codex/plugins/cache/consult/*/*/.codex-plugin/plugin.json \
		"$HOME"/.codex/plugins/cache/consult/*/.codex-plugin/plugin.json; do
		[ -f "$manifest" ] && return 0
	done
	return 1
}

cursor_consult_plugin_installed() {
	local manifest
	for manifest in "$HOME"/.cursor/plugins/cache/consult/*/*/.cursor-plugin/plugin.json \
		"$HOME"/.cursor/plugins/cache/consult/*/.cursor-plugin/plugin.json \
		"$HOME"/.cursor/plugins/local/consult/.cursor-plugin/plugin.json; do
		[ -f "$manifest" ] && return 0
	done
	return 1
}

# Codex CLI: ~/.codex/skills/
if codex_consult_plugin_installed; then
	echo "Codex: Consult plugin installed; pruning manual Consult skill links"
	remove_consult_skill_links "Codex" "$HOME/.codex/skills"
	cat <<EOF
Codex: Consult is also linked into ~/.agents/skills by this manual install.
Codex can discover ~/.agents/skills directly, so keep either the manual install
or the Codex plugin enabled, not both, to avoid duplicate Consult skills.
EOF
else
	link_skills_per_agent "Codex" "$HOME/.codex/skills"
fi

# Windsurf (Codeium Cascade): ~/.codeium/windsurf/skills/
link_skills_per_agent "Windsurf" "$HOME/.codeium/windsurf/skills"

# Google Antigravity's CLI (agy) installs plugins from a local path into
# ~/.gemini/antigravity-cli/plugins/. Consult ships plugin/ with a plugin.json
# marker and a root-level skills/ directory, which agy imports as skills.
configure_antigravity_plugin

if cursor_consult_plugin_installed; then
	cat <<EOF
Cursor: Consult plugin installed via the Cursor marketplace or ~/.cursor/plugins/local/consult.
Cursor also auto-discovers ~/.agents/skills/ from this manual install.
Keep either the Cursor plugin or the manual install for Cursor, not both, to avoid duplicate Consult skills in Agent Decides.
EOF
fi

# Pi, Cursor, Gemini CLI, OpenCode, and GitHub Copilot CLI read
# ~/.agents/skills/ directly per the agentskills.io de-facto convention; no
# per-tool symlinks needed. (Copilot CLI scans ~/.copilot, ~/.claude, and
# ~/.agents; relying on ~/.agents avoids duplicate registration with the
# ~/.claude/skills symlink above.)
echo ""
echo "Auto-discovered via ~/.agents/skills/ (no extra wiring needed):"
for tool in pi cursor gemini opencode copilot; do
	case "$tool" in
	pi) home_dir="$HOME/.pi" ;;
	cursor) home_dir="$HOME/.cursor" ;;
	gemini) home_dir="$HOME/.gemini" ;;
	opencode) home_dir="$HOME/.config/opencode" ;;
	copilot) home_dir="$HOME/.copilot" ;;
	esac
	if [ -d "$home_dir" ]; then
		echo "  - $tool ($home_dir exists)"
	else
		echo "  - $tool (not installed, will auto-discover if added)"
	fi
done
echo ""

# Commands fan-out has been removed.
#
# Modern agents (Claude Code, Codex, Cursor, Copilot CLI, Gemini CLI, OpenCode,
# Pi, Windsurf) discover skills directly from `~/.agents/skills/` and register
# the slash command from each skill's frontmatter. Linking
# `agents/.agents/commands/<name>.md` separately into `~/.claude/commands/`
# and `~/.codex/prompts/` produced duplicate `/<name>` entries in the slash
# command list: the same skill registered twice (once via SKILL.md, once via
# the standalone command file). Codex's per-skill `~/.codex/skills/<name>/`
# fan-out already namespaces cleanly as `Consult:<name>`; Claude Code's flat
# `~/.claude/skills` symlink registers the skill directly. Both made the
# extra commands link redundant.
#
# This block also prunes stale symlinks left behind by previous setup.sh
# runs that did fan out commands.
prune_stale_command_links() {
	local dir="$1"
	[ -d "$dir" ] || return 0
	local entry link_target
	for entry in "$dir"/*; do
		[ -L "$entry" ] || continue
		link_target=$(readlink "$entry")
		case "$link_target" in
		"$HOME"/.agents/commands/*)
			rm "$entry"
			echo "Removed legacy command link ${entry/#$HOME/~}"
			;;
		esac
	done
}

prune_stale_command_links "$HOME/.claude/commands"
prune_stale_command_links "$HOME/.codex/prompts"

# Sync the in-repo Claude Code / Codex plugin mirror for maintainers when
# python3 is available. End-user installs use the committed plugin mirror.
GENERATE_PLUGIN="$REPO_ROOT/scripts/generate_plugin_symlinks.py"
if [ -f "$GENERATE_PLUGIN" ] && command -v python3 >/dev/null 2>&1; then
	echo ""
	(cd "$REPO_ROOT" && python3 "$GENERATE_PLUGIN" "$REPO_ROOT")
elif [ -f "$GENERATE_PLUGIN" ]; then
	echo ""
	echo "python3 not found; skipping maintainer-only plugin sync"
fi

echo "Done."
