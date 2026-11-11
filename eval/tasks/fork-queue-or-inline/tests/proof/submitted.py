"""Per-task submitted-proof check for fork-queue-or-inline: tests that read the sent confirmations."""
import re
import sys
from pathlib import Path

sys.path.insert(0, "/tests")
from consult_lib import hidden_check_passes  # noqa: E402,F401


def read(path: Path) -> str:
    return path.read_text() if path.exists() else ""


def submitted_proof(workspace: Path) -> bool:
    tests = "\n".join(read(p) for p in sorted((workspace / "test").glob("*.js")))
    return bool(re.search(r"sentEmails|sendEmail", tests)) and bool(re.search(r"\b400\b|reject", tests, re.IGNORECASE))
