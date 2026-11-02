# Synced from eval/verifier/shared/rubric/score.py. Do not edit in tests/.
"""The rubric dimension: the score judge_runner.py wrote for this trial.

test.sh runs judge_runner.py before RewardKit. When the runner records no
score, it drops this dimension, so this criterion only runs when one exists.
"""

import json
from pathlib import Path

from rewardkit import criterion

ANSWERS_PATH = Path("/logs/verifier/judge-items.json")


@criterion
def rubric_met(workspace: Path) -> float:
    """Must-have met rate x 0.6 plus quality met rate x 0.4, unknowns left out (judge_runner.score)."""
    return float(json.loads(ANSWERS_PATH.read_text())["score"])
