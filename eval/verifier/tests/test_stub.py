"""Stub skills: the real frontmatter, a neutral body, and nothing else.

  python3 -m unittest discover eval/verifier/tests
"""

from __future__ import annotations

import shutil
import sys
import tempfile
import unittest
from pathlib import Path

EVAL_DIR = Path(__file__).resolve().parents[2]
SKILLS_DIR = EVAL_DIR.parent / "agents" / ".agents" / "skills"
sys.path.insert(0, str(EVAL_DIR / "scripts"))

import stub  # noqa: E402


def source_skills() -> dict[str, bytes]:
    return {p.parent.name: p.read_bytes() for p in SKILLS_DIR.glob("*/SKILL.md")}


def split_frontmatter(text: bytes) -> tuple[bytes, bytes]:
    end = text.index(b"\n---\n", 3) + len(b"\n---\n")
    return text[:end], text[end:]


class StubSkillsTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.built = stub.build(SKILLS_DIR, self.root / "stub-skills")

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_every_stub_keeps_its_frontmatter_byte_for_byte(self):
        for name, text in source_skills().items():
            with self.subTest(skill=name):
                stubbed = (self.built / name / "SKILL.md").read_bytes()
                self.assertEqual(split_frontmatter(stubbed)[0], split_frontmatter(text)[0])

    def test_every_stub_body_is_the_neutral_text(self):
        for name in source_skills():
            with self.subTest(skill=name):
                body = split_frontmatter((self.built / name / "SKILL.md").read_bytes())[1]
                self.assertEqual(body, f"\n# {name}\n\nThis skill has no further guidance.\n".encode())

    def test_the_stub_dir_holds_one_skill_md_per_source_skill_and_nothing_else(self):
        files = {p.relative_to(self.built).as_posix() for p in self.built.rglob("*") if p.is_file()}
        self.assertEqual(files, {f"{d.name}/SKILL.md" for d in SKILLS_DIR.iterdir() if d.is_dir()})

    def test_a_second_build_reuses_the_same_dir(self):
        self.assertEqual(stub.build(SKILLS_DIR, self.root / "stub-skills"), self.built)
        self.assertEqual([p.name for p in (self.root / "stub-skills").iterdir()], [self.built.name])

    def test_an_edited_description_builds_a_new_dir(self):
        source = self.root / "skills"
        shutil.copytree(SKILLS_DIR, source)
        skill_md = source / "proof" / "SKILL.md"
        skill_md.write_bytes(skill_md.read_bytes().replace(b"description: ", b"description: Edited. ", 1))
        self.assertNotEqual(stub.build(source, self.root / "stub-skills"), self.built)

    def test_the_snapshot_holds_every_skill_file_byte_for_byte(self):
        frozen = stub.snapshot(SKILLS_DIR, self.root / "consult-skills")
        self.assertEqual(stub.skill_files(frozen), stub.skill_files(SKILLS_DIR))


if __name__ == "__main__":
    unittest.main()
