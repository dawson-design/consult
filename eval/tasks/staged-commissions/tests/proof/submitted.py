"""Per-task submitted-proof check for staged-commissions: agent tests cover the restocking fee and the deposit."""
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
    covers_fee = bool(re.search(r"restock|fee|9000|90\.00", tests, re.IGNORECASE))
    covers_deposit = bool(re.search(r"deposit|refund", tests, re.IGNORECASE))
    return covers_fee and covers_deposit and "assert" in tests
