#!/usr/bin/env python3
"""Build the Claude Code plugin from the canonical sources.

The canonical sources are agents/.agents/core.md and agents/.agents/skills/.
This script writes two derived things:

- plugin/skills/, an exact copy of the canonical skills. Plugin installs copy
  the plugin directory, so symlinks out of it would break.
- plugin/hooks/hooks.json, whose SessionStart hook prints core.md. The text
  sits inline in a heredoc because the eval passes only hooks.json to Claude
  Code, with no plugin root to read a file from.

`--check` reports drift without writing, for tests and CI. Stdlib only.
"""

from __future__ import annotations

import filecmp
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CORE = ROOT / "agents/.agents/core.md"
SKILLS = ROOT / "agents/.agents/skills"
PLUGIN_SKILLS = ROOT / "plugin/skills"
HOOKS = ROOT / "plugin/hooks/hooks.json"
HEREDOC_END = "CONSULT_CORE"


def hook_command(core_text: str) -> str:
    """Return the shell command that prints `core_text` with one trailing newline.

    Raises ValueError when the text contains the heredoc terminator, which
    would end the heredoc early.
    """
    body = core_text.strip()
    if any(line.strip() == HEREDOC_END for line in body.splitlines()):
        raise ValueError(f"core.md contains the heredoc terminator {HEREDOC_END}")
    return f"cat <<'{HEREDOC_END}'\n{body}\n{HEREDOC_END}"


def hooks_json(core_text: str) -> str:
    """Return the hooks.json text for a SessionStart hook that prints the core."""
    hook = {"type": "command", "command": hook_command(core_text)}
    return json.dumps({"hooks": {"SessionStart": [{"hooks": [hook]}]}}, indent=2) + "\n"


def mirror_drift(src: Path, dest: Path) -> list[str]:
    """Return the relative paths that differ between two directory trees."""
    if not dest.exists():
        return ["(plugin/skills missing)"]
    cmp = filecmp.dircmp(src, dest)
    return _drift(cmp, Path())


def _drift(cmp: filecmp.dircmp[str], rel: Path) -> list[str]:
    diffs = [str(rel / name) for name in cmp.left_only + cmp.right_only + cmp.diff_files + cmp.funny_files]
    for name, sub in cmp.subdirs.items():
        diffs.extend(_drift(sub, rel / name))
    return diffs


def check() -> list[str]:
    """Return a list of drift problems; empty when the plugin is current."""
    problems = [f"plugin/skills differs: {path}" for path in mirror_drift(SKILLS, PLUGIN_SKILLS)]
    expected = hooks_json(CORE.read_text(encoding="utf8"))
    if not HOOKS.exists() or HOOKS.read_text(encoding="utf8") != expected:
        problems.append("plugin/hooks/hooks.json is out of date")
    return problems


def build() -> None:
    """Rewrite plugin/skills and plugin/hooks/hooks.json from the sources."""
    if PLUGIN_SKILLS.exists():
        shutil.rmtree(PLUGIN_SKILLS)
    shutil.copytree(SKILLS, PLUGIN_SKILLS, ignore=shutil.ignore_patterns(".DS_Store"))
    HOOKS.parent.mkdir(parents=True, exist_ok=True)
    HOOKS.write_text(hooks_json(CORE.read_text(encoding="utf8")), encoding="utf8")


def main(argv: list[str]) -> int:
    if "--check" in argv:
        problems = check()
        for problem in problems:
            print(problem, file=sys.stderr)
        return 1 if problems else 0
    build()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
