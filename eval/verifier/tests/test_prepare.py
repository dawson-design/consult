"""The verifier's prepare step: judge inputs inlined, or the judge dropped.

  python3 -m unittest discover eval/verifier/tests
"""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

EVAL_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(EVAL_DIR / "verifier" / "shared"))

import consult_lib as cl  # noqa: E402

JUDGE_ENV = {"CLAUDE_CODE_OAUTH_TOKEN": "token", "REWARDKIT_JUDGE": "claude-code"}


class PrepareTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        root = Path(self._tmp.name)
        self.tests = root / "tests"
        shutil.copytree(EVAL_DIR / "tasks" / "api-error-contract" / "tests", self.tests)
        self.bundle = root / "judge-bundle.md"
        self.bundle.write_text("# Changes against the starting repository\n\nDIFF-MARKER\n")

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def prepare(self, env: dict) -> None:
        with mock.patch.dict(os.environ, env, clear=True), mock.patch.object(cl, "BUNDLE_PATH", self.bundle):
            cl.prepare_tests(self.tests)

    def test_the_claude_code_judge_gets_the_instruction_and_bundle_inline(self):
        self.prepare(JUDGE_ENV)
        prompt = (self.tests / "judge" / "prompt.md").read_text()
        self.assertIn("{criteria}", prompt)
        self.assertIn("handleUserLookup", prompt)
        self.assertIn("DIFF-MARKER", prompt)

    def test_a_bundle_over_the_argument_limit_stays_on_disk(self):
        self.bundle.write_text("DIFF-MARKER\n" + "x" * (cl.INLINE_BUNDLE_LIMIT + 1))
        self.prepare(JUDGE_ENV)
        self.assertNotIn("DIFF-MARKER", (self.tests / "judge" / "prompt.md").read_text())

    def test_an_llm_judge_override_keeps_the_template_and_reads_files(self):
        self.prepare({**JUDGE_ENV, "REWARDKIT_JUDGE": "openai/gpt-5.5", "OPENAI_API_KEY": "key"})
        self.assertNotIn("DIFF-MARKER", (self.tests / "judge" / "prompt.md").read_text())

    def test_skipping_the_judge_removes_it_from_the_reward(self):
        self.prepare({**JUDGE_ENV, "CONSULT_EVAL_SKIP_JUDGE": "1"})
        self.assertFalse((self.tests / "judge").exists())
        self.assertNotIn("judge", (self.tests / "reward.toml").read_text().split("weights")[1])


if __name__ == "__main__":
    unittest.main()
