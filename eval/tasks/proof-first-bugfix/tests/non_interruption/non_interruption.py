# Synced from eval/verifier/shared/non_interruption/non_interruption.py. Do not edit in tests/.
import sys
from pathlib import Path

sys.path.insert(0, "/tests")
import consult_lib as cl
from rewardkit import criterion


@criterion
def non_interruption_score(workspace: Path) -> float:
    """1 minus 0.25 per agent message that ends by asking a question. Zero-weight readout."""
    turns = cl.TESTS_DIR / "rubric" / "instruction.md"
    instruction = turns.read_text() if turns.is_file() else ""
    proposal_turn = bool(cl.load_task_meta().get("proposal_turn"))
    questions = cl.question_message_count(cl.load_trajectory(), proposal_turn, instruction)
    return max(0.0, 1.0 - 0.25 * questions)
