"""Parse the judge bundle that consult_lib.build_bundle writes for each trial.

The bundle is the trial's diff against the starting repository, each new file,
and the final agent message, as Markdown. rescore.py rebuilds a workspace from
it, and lift.py counts the lines a trial changed. The format belongs to
verifier/shared/consult_lib.py; this module is the one parser of it.
Standard library only, so the tests run in CI.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

BUNDLE_HEAD = "# Changes against the starting repository\n\n## Diff\n\n```diff\n"
NEW_FILE_HEAD = "## New file: "
FINAL_HEAD = "## Final agent message\n\n"
# consult_lib.build_bundle closes each fenced block with "\n```\n\n" before the next section header.
SECTION_BREAK_RE = re.compile(r"\n```\n\n(?=## New file: [^\n]+\n\n```\n|## Final agent message\n\n)")


class RebuildError(ValueError):
    """The workspace cannot be rebuilt: no bundle, a truncated or malformed one, or a diff that does not apply."""


@dataclass(frozen=True)
class Bundle:
    diff: str
    new_files: tuple[tuple[str, str], ...]


def parse_bundle(text: str) -> Bundle:
    """The diff and new files consult_lib.build_bundle wrote; RebuildError when truncated or malformed."""
    if not text.startswith(BUNDLE_HEAD):
        raise RebuildError("bundle does not start with the diff section")
    blocks = SECTION_BREAK_RE.split(text[len(BUNDLE_HEAD) - 1:])
    if len(blocks) < 2 or not blocks[-1].startswith(FINAL_HEAD):
        raise RebuildError("bundle is truncated: no final agent message section")
    return Bundle(diff=blocks[0][1:], new_files=tuple(parse_new_file(b) for b in blocks[1:-1]))


def parse_new_file(block: str) -> tuple[str, str]:
    header, fence, content = block.partition("\n\n```\n")
    if not header.startswith(NEW_FILE_HEAD) or not fence:
        raise RebuildError(f"bundle has a malformed section: {header[:80]!r}")
    return header[len(NEW_FILE_HEAD):], content
