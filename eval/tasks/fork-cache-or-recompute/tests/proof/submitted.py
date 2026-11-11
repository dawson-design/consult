"""Per-task submitted-proof check for fork-cache-or-recompute: tests for the summary endpoint."""
import re
import sys
from pathlib import Path

sys.path.insert(0, "/tests")
from consult_lib import hidden_check_passes  # noqa: E402,F401


def read(path: Path) -> str:
    return path.read_text() if path.exists() else ""


def submitted_proof(workspace: Path) -> bool:
    tests = "\n".join(read(p) for p in sorted((workspace / "test").glob("*.js")))
    return all(re.search(p, tests) for p in (r"summary", r"lowestPrice", r"inStock"))
