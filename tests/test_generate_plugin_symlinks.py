"""The plugin mirror generator's CLI: copying skills into plugin/skills safely.

Each test builds a scratch repo with canonical skills under
agents/.agents/skills and runs the generator against it.
"""

from __future__ import annotations

import unittest
from pathlib import Path

from helpers import ROOT, TempDirTestCase, run

# The implementation under test. Step 3 of docs/plans/python-only-tooling.md
# switches this to the Python port and reads MIRROR_DESTS from it.
COMMAND = ["node", ROOT / "scripts/generate-plugin-symlinks.mjs"]
MIRROR_DESTS = ["plugin/skills"]


def make_skill(root: Path, name: str) -> Path:
    """Create a canonical skill with a one-line SKILL.md and return its directory."""
    skill = root / "agents/.agents/skills" / name
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text(f"# {name}\n", encoding="utf8")
    return skill


class GeneratePluginSymlinksTests(TempDirTestCase):
    def generate(self):
        return run([*COMMAND, self.tmp])

    def canonical(self, name: str) -> str:
        return (self.tmp / "agents/.agents/skills" / name / "SKILL.md").read_text(encoding="utf8")

    def test_writes_every_declared_mirror_destination(self) -> None:
        make_skill(self.tmp, "code-review")

        result = self.generate()

        self.assertEqual(result.returncode, 0, result.stderr)
        for dest in MIRROR_DESTS:
            copy = (self.tmp / dest / "code-review/SKILL.md").read_text(encoding="utf8")
            self.assertEqual(copy, self.canonical("code-review"))

    def test_creates_real_plugin_copies_for_skills(self) -> None:
        make_skill(self.tmp, "code-review")

        result = self.generate()

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("plugin skill mirror in sync", result.stdout)
        copy = self.tmp / "plugin/skills/code-review"
        self.assertFalse(copy.is_symlink())
        self.assertEqual((copy / "SKILL.md").read_text(encoding="utf8"), self.canonical("code-review"))

    def test_removes_stale_generated_entries_without_removing_real_files(self) -> None:
        make_skill(self.tmp, "code-review")
        plugin_skills = self.tmp / "plugin/skills"
        plugin_skills.mkdir(parents=True)
        (plugin_skills / "old").symlink_to("../../agents/.agents/skills/old")
        (plugin_skills / "local-note").write_text("keep me\n", encoding="utf8")

        result = self.generate()

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("removed stale plugin entry: plugin/skills/old", result.stdout)
        self.assertIn("plugin/skills/local-note is not a generated directory", result.stderr)
        self.assertEqual((plugin_skills / "local-note").read_text(encoding="utf8"), "keep me\n")

    def test_refuses_to_overwrite_real_plugin_entries(self) -> None:
        make_skill(self.tmp, "code-review")
        conflict = self.tmp / "plugin/skills/code-review"
        conflict.parent.mkdir(parents=True)
        conflict.write_text("not a symlink\n", encoding="utf8")

        result = self.generate()

        self.assertEqual(result.returncode, 1)
        self.assertEqual(conflict.read_text(encoding="utf8"), "not a symlink\n")
        self.assertIn("plugin/skills/code-review exists as a real file/dir", result.stderr)

    def test_rejects_paths_that_are_not_repo_roots(self) -> None:
        result = self.generate()

        self.assertEqual(result.returncode, 2)
        self.assertIn("not a repo root", result.stderr)


if __name__ == "__main__":
    unittest.main()
