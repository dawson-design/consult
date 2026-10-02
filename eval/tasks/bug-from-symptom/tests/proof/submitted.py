"""Per-task submitted-proof check for bug-from-symptom: an agent-written test that pins the aliasing."""
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
    return bool(re.search(r"duplicate|save", tests)) and bool(re.search(r"config|range", tests)) and "assert" in tests
