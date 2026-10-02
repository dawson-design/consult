"""Per-task submitted-proof check for money-field-change: agent tests cover another currency and the old total."""
import re
import sys
from pathlib import Path

sys.path.insert(0, "/tests")
from consult_lib import changed_paths, classify, hidden_check_passes  # noqa: E402,F401


def submitted_proof(workspace: Path) -> bool:
    tests = " ".join(
        (workspace / p).read_text() for p in changed_paths(workspace)
        if classify(p) == "test" and (workspace / p).is_file()
    )
    return bool(re.search(r"\b(CAD|GBP)\b", tests)) and bool(re.search(r"\btotal\b", tests)) and "assert" in tests
