# Synced from eval/verifier/shared/rules/rules.py. Do not edit in tests/.
"""One criterion per rule id in consult.json `rules`, named by the id. Zero-weight readout."""
import sys
from pathlib import Path

sys.path.insert(0, "/tests")
import consult_lib as cl  # noqa: E402
import consult_rules as cr  # noqa: E402
from rewardkit import criteria, criterion  # noqa: E402


@criterion
def rule_check(workspace: Path, rule_id: str) -> float:
    return cr.score(rule_id, workspace)


@criterion
def no_rules(workspace: Path, reason: str) -> float:
    """Placeholder so a task without rules still yields this dimension for reward.toml."""
    return 1.0


RULE_IDS = cr.scored_rule_ids(cl.load_task_meta().get("rules") or [])
for rule_id in RULE_IDS:
    criteria.rule_check(rule_id, name=rule_id)
if not RULE_IDS:
    criteria.no_rules("task lists no rules", name="no_rules")
