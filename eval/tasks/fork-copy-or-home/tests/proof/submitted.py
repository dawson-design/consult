"""Per-task submitted-proof check for fork-copy-or-home: a test of responseDueBy over a weekend or a holiday."""

import re
import sys
from pathlib import Path

sys.path.insert(0, "/tests")
from consult_lib import hidden_check_passes  # noqa: E402,F401


def submitted_proof(workspace: Path) -> bool:
    test_dir = workspace / "test"
    combined = ""
    if test_dir.is_dir():
        for entry in sorted(test_dir.iterdir()):
            if entry.suffix in (".js", ".mjs"):
                combined += "\n" + entry.read_text(errors="replace")
    return bool(re.search(r"\bresponseDueBy\b", combined)) and bool(
        re.search(r"weekend|holiday|saturday|sunday|2026-11-2[5-7]|2026-03-0[78]", combined, re.IGNORECASE)
    )
