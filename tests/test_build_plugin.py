"""Tests for scripts/build_plugin.py: the SessionStart hook prints core.md
exactly, and the committed plugin matches the canonical sources."""

import json
import subprocess

import build_plugin
import pytest


def run_hook(command: str) -> str:
    """Run a hook command the way Claude Code does, with a POSIX sh."""
    return subprocess.run(["sh", "-c", command], capture_output=True, text=True, check=True).stdout


def test_hook_prints_text_with_one_trailing_newline() -> None:
    text = "Consult is installed.\n\n# Core\n\n`code` and 'quotes' and $HOME stay literal.\n\n\n"

    assert run_hook(build_plugin.hook_command(text)) == text.strip() + "\n"


def test_hook_refuses_text_containing_the_heredoc_terminator() -> None:
    with pytest.raises(ValueError, match="terminator"):
        build_plugin.hook_command(f"before\n{build_plugin.HEREDOC_END}\nafter")


def test_committed_hook_prints_core_md_verbatim() -> None:
    hooks = json.loads(build_plugin.HOOKS.read_text(encoding="utf8"))
    command = hooks["hooks"]["SessionStart"][0]["hooks"][0]["command"]

    assert run_hook(command) == build_plugin.CORE.read_text(encoding="utf8").strip() + "\n"


def test_committed_plugin_matches_sources() -> None:
    assert build_plugin.check() == []
