"""Placebo core: the hook settings that print rules no eval check scores.

The placebo arm installs the stub skills, as the stub arm does, but its
SessionStart hook prints placebo/core.md in place of agents/.agents/core.md.
That file keeps the core's opening paragraph byte for byte, so skill loading
matches the stub arm, and puts formatting rules in the core's section shape
and length. Stub minus placebo is then the effect of what the core says, and
placebo minus bare the effect of printing any rules at all.

The settings JSON comes from scripts/build_plugin.py's hooks_json, the
function that writes plugin/hooks/hooks.json, and lands under a content hash
as stub.py writes its builds. Standard library only, so the tests run in CI.
"""

from __future__ import annotations

import sys
from pathlib import Path

import stub

EVAL_DIR = Path(__file__).resolve().parent.parent
CORE = EVAL_DIR / "placebo" / "core.md"
HOOKS_FILE = "hooks.json"

sys.path.insert(0, str(EVAL_DIR.parent / "scripts"))
import build_plugin


def hooks_json() -> str:
    """The hooks.json text whose SessionStart hook prints the placebo core."""
    return build_plugin.hooks_json(CORE.read_text(encoding="utf8"))


def build(root: Path) -> Path:
    """The placebo hooks.json at root/<content hash>/; an existing one is reused."""
    return stub.write_tree({HOOKS_FILE: hooks_json().encode()}, root) / HOOKS_FILE
