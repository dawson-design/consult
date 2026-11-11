"""Per-task submitted-proof check for fork-retry-or-timeout: tests for the carrier failing and hanging."""
import re
import sys
from pathlib import Path

sys.path.insert(0, "/tests")
from consult_lib import hidden_check_passes  # noqa: E402,F401


def read(path: Path) -> str:
    return path.read_text() if path.exists() else ""


def submitted_proof(workspace: Path) -> bool:
    tests = "\n".join(read(p) for p in sorted((workspace / "test").glob("*.js")))
    return bool(re.search(r"\b503\b", tests)) and bool(re.search(r"hang|slow|timeout|timed? out|never (answers|responds)", tests, re.IGNORECASE))
