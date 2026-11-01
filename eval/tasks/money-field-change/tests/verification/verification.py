# Synced from eval/verifier/shared/verification/verification.py. Do not edit in tests/.
import sys
from pathlib import Path

sys.path.insert(0, "/tests")
import consult_lib as cl
from rewardkit import criterion


@criterion
def visible_tests_pass(workspace: Path) -> bool:
    return cl.visible_tests_pass(workspace, cl.load_task_meta())


@criterion
def hidden_check_passes(workspace: Path) -> bool:
    return cl.hidden_check_passes(workspace)
