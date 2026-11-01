"""The CI workflow's supply-chain guards: every action pinned to a commit, and a read-only token.

The workflow is read with regular expressions over the standard library rather
than parsed as YAML, because the repo's tooling is stdlib only.
"""

from __future__ import annotations

import re
import unittest

from helpers import ROOT

WORKFLOW = ROOT / ".github/workflows/ci.yml"
# `uses: <ref>` with the version the SHA stands for in a trailing comment.
USES_RE = re.compile(r"^\s*-?\s*uses:\s*(\S+)(?:\s+#\s*(\S+))?")
# owner/repo[/path]@<40-hex commit>. A tag or branch after the @ can be moved.
PINNED_RE = re.compile(r"^[\w.-]+/[\w.-]+(?:/[\w./-]+)?@[0-9a-f]{40}$")
# A `permissions:` key at any indent: a scalar on the line, or a mapping indented below it.
PERMISSIONS_RE = re.compile(r"^([ \t]*)permissions:[ \t]*(\S*)[ \t]*\n((?:\1[ \t]+\S.*\n)*)", re.MULTILINE)
VERSION_COMMENT_RE = re.compile(r"v\d[\w.-]*")
READ_ONLY = {"read", "none", "read-all", "{}"}


def action_references(text: str) -> list[tuple[str, str]]:
    """Every (`uses:` reference, trailing comment) pair in the workflow, in order; "" when there is no comment."""
    return [(match[1], match[2] or "") for line in text.splitlines() if (match := USES_RE.match(line))]


def grant_values(block: str) -> list[str]:
    """Access levels in an indented permissions mapping; comment lines and trailing comments are skipped."""
    values = []
    for line in block.splitlines():
        entry = line.split("#", 1)[0].strip()
        if ":" in entry:
            values.append(entry.split(":", 1)[1].strip())
    return values


def permission_grants(text: str) -> list[str]:
    """Every access level any `permissions:` key grants, at the workflow or a job: scalars and mapping values."""
    grants = []
    for match in PERMISSIONS_RE.finditer(text):
        if match[2]:
            grants.append(match[2])
        grants.extend(grant_values(match[3]))
    return grants


class CiWorkflowTests(unittest.TestCase):
    def test_every_action_is_pinned_to_a_commit_with_its_version_noted(self) -> None:
        references = action_references(WORKFLOW.read_text(encoding="utf8"))

        self.assertTrue(references, "no `uses:` lines found")
        self.assertEqual([ref for ref, _ in references if not PINNED_RE.match(ref)], [])
        self.assertEqual([ref for ref, comment in references if not VERSION_COMMENT_RE.fullmatch(comment)], [])

    def test_the_workflow_token_grants_read_access_only(self) -> None:
        grants = permission_grants(WORKFLOW.read_text(encoding="utf8"))

        self.assertTrue(grants, "no permissions key found")
        self.assertEqual(set(grants) - READ_ONLY, set())

    def test_permission_grants_sees_a_job_level_scalar_and_mapping(self) -> None:
        text = (
            "permissions:\n  # why\n  contents: read # scope\njobs:\n  a:\n    permissions: write-all\n"
            "  b:\n    permissions:\n      issues: write\n"
        )

        self.assertEqual(permission_grants(text), ["read", "write-all", "write"])


if __name__ == "__main__":
    unittest.main()
