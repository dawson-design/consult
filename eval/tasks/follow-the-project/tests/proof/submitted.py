"""Per-task submitted-proof check for follow-the-project: agent tests cover overdrawing a card and overpaying an order."""
import re
import sys
from pathlib import Path

sys.path.insert(0, "/tests")
from consult_lib import changed_paths, classify, hidden_check_passes  # noqa: E402,F401


def submitted_proof(workspace: Path) -> bool:
    tests = " ".join(
        (workspace / p).read_text(errors="replace") for p in changed_paths(workspace)
        if classify(p) == "test" and (workspace / p).is_file()
    )
    covers_card = bool(re.search(r"gift", tests, re.IGNORECASE))
    covers_limits = bool(re.search(r"balance|Conflict|409|below zero|too low|exceed", tests, re.IGNORECASE))
    return covers_card and covers_limits and "assert" in tests
