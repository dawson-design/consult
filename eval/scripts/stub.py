"""Stub skills: the Consult skill listing with no guidance behind it.

The stub arm installs these in place of the real skills, with the same hook.
Each stub keeps its skill's SKILL.md frontmatter byte for byte, so the agent
sees the same names and descriptions, but the body says nothing and no
reference files ship. Consult minus stub is then the effect of skill content,
and stub minus bare the effect of the listing and hook.

snapshot freezes the real skills once per run. The consult arm reads that copy
and the stubs are built from it, so both arms see the same listing however long
the run takes. Standard library only, so the tests run in CI.
"""

from __future__ import annotations

import hashlib
import re
import tempfile
from pathlib import Path

SKILL_FILE = "SKILL.md"
FRONTMATTER_RE = re.compile(rb"\A---\n.*?\n---\n", re.DOTALL)


def neutral_body(name: str) -> bytes:
    return f"\n# {name}\n\nThis skill has no further guidance.\n".encode()


def stub_skill(skill_md: Path) -> bytes:
    """The skill's frontmatter unchanged, then the neutral body."""
    match = FRONTMATTER_RE.match(skill_md.read_bytes())
    if not match:
        raise ValueError(f"{skill_md} has no YAML frontmatter block")
    return match.group(0) + neutral_body(skill_md.parent.name)


def stub_files(source: Path) -> dict[str, bytes]:
    """relative path -> stub SKILL.md bytes, for every skill dir under source."""
    return {f"{path.parent.name}/{SKILL_FILE}": stub_skill(path) for path in sorted(source.glob(f"*/{SKILL_FILE}"))}


def skill_files(source: Path) -> dict[str, bytes]:
    """relative path -> bytes, for every file under source."""
    return {path.relative_to(source).as_posix(): path.read_bytes() for path in sorted(source.rglob("*")) if path.is_file()}


def content_hash(files: dict[str, bytes]) -> str:
    digest = hashlib.sha256()
    for path, data in sorted(files.items()):
        digest.update(path.encode() + b"\0" + data + b"\0")
    return digest.hexdigest()[:16]


def build(source: Path, root: Path) -> Path:
    """The stub skills dir for source, at root/<content hash>; an existing one is reused."""
    return write_tree(stub_files(source), root)


def snapshot(source: Path, root: Path) -> Path:
    """A frozen copy of every file under source, at root/<content hash>; an existing one is reused."""
    return write_tree(skill_files(source), root)


def write_tree(files: dict[str, bytes], root: Path) -> Path:
    dest = root / content_hash(files)
    if dest.is_dir():
        return dest
    root.mkdir(parents=True, exist_ok=True)
    # Written aside and renamed, so an interrupted build never leaves a partial dir a later run would reuse.
    staging = Path(tempfile.mkdtemp(dir=root, prefix=".staging-"))
    for path, data in files.items():
        (staging / path).parent.mkdir(parents=True, exist_ok=True)
        (staging / path).write_bytes(data)
    staging.rename(dest)
    return dest
