"""The plugin generator's CLI: the core's workflow copy, the plugin/skills mirror, and the SessionStart hook.

Each test builds a scratch repo with canonical skills under
agents/.agents/skills and runs the generator against it.
"""

from __future__ import annotations

import json
import os
import unittest
from pathlib import Path

from helpers import ROOT, TempDirTestCase, load_script, run

COMMAND = ["python3", ROOT / "scripts/generate_plugin_symlinks.py"]
generator = load_script("generate_plugin_symlinks")
HOOK_SOURCE = generator.HOOK_SOURCE
CORE_COPY = generator.CORE_COPY
HOOK_DEST = generator.HOOK_DEST
MAX_HOOK_CHARS = generator.MAX_HOOK_CHARS


def make_skill(root: Path, name: str) -> Path:
    """Create a canonical skill with a one-line SKILL.md and return its directory."""
    skill = root / "agents/.agents/skills" / name
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text(f"# {name}\n", encoding="utf8")
    return skill


def write_core(root: Path, text: str) -> None:
    """Write `text` as the hook source, core.md, under `root`."""
    path = root / HOOK_SOURCE
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf8")


def hook_command(root: Path) -> str:
    """Return the single SessionStart command from the generated hooks.json."""
    hooks_file = json.loads((root / HOOK_DEST).read_text(encoding="utf8"))
    return hooks_file["hooks"]["SessionStart"][0]["hooks"][0]["command"]


class GeneratePluginSymlinksTests(TempDirTestCase):
    def generate(self):
        return run([*COMMAND, self.tmp])

    def canonical(self, name: str) -> str:
        return (self.tmp / "agents/.agents/skills" / name / "SKILL.md").read_text(encoding="utf8")

    def test_writes_every_declared_mirror_destination(self) -> None:
        # The validator reads this list to find mirrors to check, so dropping
        # a destination would silently stop its drift check.
        self.assertEqual(generator.MIRROR_DESTS, ["plugin/skills"])
        make_skill(self.tmp, "code-review")

        result = self.generate()

        self.assertEqual(result.returncode, 0, result.stderr)
        for dest in generator.MIRROR_DESTS:
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

    def test_copies_a_symlinked_skill_as_the_same_symlink(self) -> None:
        make_skill(self.tmp, "code-review")
        (self.tmp / "agents/.agents/skills/review").symlink_to("code-review")

        result = self.generate()

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(os.readlink(self.tmp / "plugin/skills/review"), "code-review")

    def test_removes_stale_generated_entries_without_removing_real_files(self) -> None:
        make_skill(self.tmp, "code-review")
        plugin_skills = self.tmp / "plugin/skills"
        plugin_skills.mkdir(parents=True)
        (plugin_skills / "old").symlink_to("../../agents/.agents/skills/old")
        (plugin_skills / "local-note").write_text("keep me\n", encoding="utf8")

        result = self.generate()

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("removed stale plugin entry: plugin/skills/old", result.stdout)
        self.assertFalse(os.path.lexists(plugin_skills / "old"))
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

    def test_generates_a_session_start_hook_that_prints_core_md_without_shell_expansion(self) -> None:
        make_skill(self.tmp, "workflow")
        write_core(self.tmp, "Consult is installed.\r\n\nKeep `$HOME`, \"quotes\", 'apostrophes', and \\n literal.\n")

        result = self.generate()

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(f"generated {HOOK_DEST} from {HOOK_SOURCE}", result.stdout)
        core = (self.tmp / HOOK_SOURCE).read_bytes()
        self.assertEqual((self.tmp / CORE_COPY).read_bytes(), core)
        mirror = CORE_COPY.replace("agents/.agents/skills/", "plugin/skills/")
        self.assertEqual((self.tmp / mirror).read_bytes(), core)
        printed = run(["sh", "-c", hook_command(self.tmp)], cwd=self.tmp)
        self.assertEqual(printed.returncode, 0, printed.stderr)
        expected = "Consult is installed.\n\nKeep `$HOME`, \"quotes\", 'apostrophes', and \\n literal.\n"
        self.assertEqual(printed.stdout, expected)

    def test_drops_a_byte_order_mark_from_the_hook_text(self) -> None:
        make_skill(self.tmp, "workflow")
        write_core(self.tmp, "\ufeffConsult is installed.\n")

        result = self.generate()

        self.assertEqual(result.returncode, 0, result.stderr)
        printed = run(["sh", "-c", hook_command(self.tmp)], cwd=self.tmp)
        self.assertEqual(printed.stdout, "Consult is installed.\n")

    def test_refuses_an_unusable_core_md_and_writes_no_hook(self) -> None:
        cases = [
            (
                "has a line that would end the heredoc",
                "Consult is installed.\nCONSULT_CORE\nmore\n",
                "has a line equal to CONSULT_CORE",
            ),
            (
                "is longer than the hook allows",
                f"Consult is installed. {'x' * MAX_HOOK_CHARS}\n",
                "the SessionStart hook allows",
            ),
            ("is empty", "  \n", "is empty"),
        ]
        for label, core, message in cases:
            with self.subTest(label):
                make_skill(self.tmp / label, "workflow")
                write_core(self.tmp / label, core)

                result = run([*COMMAND, self.tmp / label])

                self.assertEqual(result.returncode, 1)
                self.assertIn(message, result.stderr)
                self.assertFalse((self.tmp / label / HOOK_DEST).exists())

    def test_leaves_the_hooks_file_alone_when_core_md_is_absent(self) -> None:
        make_skill(self.tmp, "code-review")

        result = self.generate()

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(f"no {HOOK_SOURCE}; left {HOOK_DEST} unchanged", result.stdout)
        self.assertFalse((self.tmp / HOOK_DEST).exists())

    def test_rejects_paths_that_are_not_repo_roots(self) -> None:
        result = self.generate()

        self.assertEqual(result.returncode, 2)
        self.assertIn("not a repo root", result.stderr)


if __name__ == "__main__":
    unittest.main()
