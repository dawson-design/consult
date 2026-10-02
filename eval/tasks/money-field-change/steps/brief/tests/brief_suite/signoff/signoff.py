# Synced from eval/verifier/shared/signoff/signoff.py. Do not edit in tests/.
"""Step-1 sign-off: one criterion per sign-off rule the task lists, plus zero-weight mode flags."""
import sys
from pathlib import Path

sys.path.insert(0, "/tests")
import consult_lib as cl  # noqa: E402
import consult_rules as cr  # noqa: E402
from rewardkit import criteria, criterion  # noqa: E402

MODES = ("stopped", "provisional", "built")


@criterion
def signoff_rule(workspace: Path, rule_id: str) -> float:
    return cr.score(rule_id, workspace)


@criterion
def signoff_mode_is(workspace: Path, mode: str) -> float:
    """1 when the step-1 outcome was this mode; lift.py reads the three flags as signoff_mode."""
    try:
        return 1.0 if cr.signoff_mode(workspace, cl.load_trajectory(), cl.load_task_meta()) == mode else 0.0
    except Exception:  # noqa: BLE001
        return 0.0


for rule_id in [r for r in cl.load_task_meta().get("rules") or [] if r in cr.SIGNOFF_RULES]:
    criteria.signoff_rule(rule_id, name=rule_id)
for mode in MODES:
    criteria.signoff_mode_is(mode, name=f"mode_{mode}", weight=0.0)
