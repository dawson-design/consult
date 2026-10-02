"""Per-task submitted-proof check for service-from-brief: agent tests cover redirects and refused targets."""
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
    return bool(re.search(r"30[12378]|redirect", tests)) and bool(re.search(r"javascript:|data:", tests)) and "assert" in tests
