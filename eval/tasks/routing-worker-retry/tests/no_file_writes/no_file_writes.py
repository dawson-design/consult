# Synced from eval/verifier/shared/no_file_writes/no_file_writes.py. Do not edit in tests/.
import sys
from pathlib import Path

sys.path.insert(0, "/tests")
import consult_lib as cl
from rewardkit import criterion


@criterion
def workspace_unchanged(workspace: Path) -> bool:
    return not cl.changed_paths(workspace)


@criterion
def no_write_tool_calls(workspace: Path) -> bool:
    return not any(cl.is_write_call(c) for c in cl.load_trajectory().calls)
