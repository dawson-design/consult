"""The proof dimension's post-write check: a test run after the last workspace edit.

  python3 -m unittest discover eval/verifier/tests

Fixtures follow Claude Code trajectories: `Bash` commands and `Write` or
`Edit` calls with absolute /app paths, several calls to a step when the agent
issues them together.
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "shared"))

import consult_lib as cl  # noqa: E402


def bash(command: str) -> dict:
    return {"function_name": "Bash", "arguments": {"command": command}}


def write(path: str) -> dict:
    return {"function_name": "Write", "arguments": {"file_path": path, "content": "x"}}


def edit(path: str) -> dict:
    return {"function_name": "Edit", "arguments": {"file_path": path, "old_string": "a", "new_string": "b"}}


def step(*calls: dict) -> dict:
    """One agent step; its calls get ids in order, like a parallel tool-use turn."""
    tool_calls = [{"tool_call_id": f"c{i}", **call} for i, call in enumerate(calls)]
    return {"source": "agent", "message": "", "tool_calls": tool_calls}


def proved(*steps: dict, visible_test_cmd: str | None = None) -> bool:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "trajectory.json"
        path.write_text(json.dumps({"steps": [{"step_id": i, **s} for i, s in enumerate(steps, start=1)]}))
        return cl.has_post_write_proof(cl.load_trajectory(path), visible_test_cmd)


FIX = write("/app/src/cart.js")
TEST = bash("npm test 2>&1 | tail -5")


class OrderTests(unittest.TestCase):
    def test_a_test_later_in_the_same_step_proves_the_edit(self):
        self.assertTrue(proved(step(FIX, TEST)))
        self.assertFalse(proved(step(TEST, FIX)))

    def test_an_edit_after_the_last_test_is_unproven(self):
        self.assertTrue(proved(step(FIX), step(TEST)))
        self.assertFalse(proved(step(FIX), step(TEST), step(edit("/app/README.md"))))

    def test_no_workspace_edit_is_no_post_write_proof(self):
        self.assertFalse(proved(step(TEST)))


class WorkspaceWriteTests(unittest.TestCase):
    def test_edit_tools_count_only_under_app(self):
        self.assertTrue(proved(step(FIX), step(TEST), step(write("/tmp/probe.mjs"))))
        self.assertFalse(proved(step(FIX), step(TEST), step(edit("/app/test/cart.test.js"))))

    def test_shell_writes_to_tmp_dev_null_or_a_variable_do_not_count(self):
        scratch = bash('node probe.js > /tmp/out.log 2>&1; echo x >/dev/null; echo y > "$TMPDIR/a"; echo z > $d/b')
        self.assertTrue(proved(step(FIX), step(TEST), step(scratch)))
        self.assertFalse(proved(step(FIX), step(TEST), step(bash('echo "export {}" > src/extra.js'))))

    def test_relative_writes_after_cd_out_of_app_do_not_count(self):
        copy = bash("rm -rf /tmp/rv && cp -r /app /tmp/rv && cd /tmp/rv && sed -i 's/a/b/' src/cart.js")
        self.assertTrue(proved(step(FIX), step(TEST), step(copy)))
        back = bash("cd /tmp && echo x > a.txt && cd /app && sed -i 's/a/b/' src/cart.js")
        self.assertFalse(proved(step(FIX), step(TEST), step(back)))

    def test_sed_and_perl_in_place_edits_count_by_their_file_operand(self):
        self.assertTrue(proved(step(FIX), step(TEST), step(bash("sed -i 's/a/b/' /tmp/cart.js"))))
        self.assertFalse(proved(step(FIX), step(TEST), step(bash("perl -0pi -e 's/a/b/' src/cart.js"))))

    def test_a_heredoc_body_is_not_shell_syntax(self):
        scratch = bash("cat > /tmp/probe.mjs <<'EOF'\nconst ok = a > b;\necho x > src/cart.js\nEOF\nnode /tmp/probe.mjs")
        self.assertTrue(proved(step(FIX), step(TEST), step(scratch)))
        self.assertFalse(proved(step(FIX), step(TEST), step(bash("cat >> /app/test/cart.test.js <<'EOF'\ntest();\nEOF"))))

    def test_an_inline_script_that_writes_a_file_is_an_edit(self):
        reader = bash("python3 - <<'EOF'\nprint(open('src/cart.js').read())\nEOF")
        self.assertTrue(proved(step(FIX), step(TEST), step(reader)))
        writer = bash("python3 - <<'EOF'\np = 'src/cart.js'\ns = open(p).read()\nopen(p, 'w').write(s)\nEOF")
        self.assertFalse(proved(step(FIX), step(TEST), step(writer)))

    def test_an_inline_script_counts_by_its_write_target(self):
        for scratch in (
            "python3 -c \"open('/tmp/out.json','w').write('{}')\"",
            "node -e \"require('fs').writeFileSync('/tmp/x.json','{}')\"",
            "python3 - <<'EOF'\nimport json\nopen('/tmp/report.json', 'w').write('{}')\nEOF",
            "python3 -c \"p='/tmp/mut/src/cart.js'; s=open(p).read(); open(p,'w').write(s)\"",
        ):
            self.assertTrue(proved(step(FIX), step(TEST), step(bash(scratch))), scratch)
        writer = bash("node -e \"require('fs').writeFileSync('src/cart.js','x')\"")
        self.assertFalse(proved(step(FIX), step(TEST), step(writer)))

    def test_an_in_place_edit_on_piped_file_names_counts_in_the_current_directory(self):
        scratch = bash("cd /tmp/rv && grep -rl foo . | xargs sed -i 's/foo/bar/g'")
        self.assertTrue(proved(step(FIX), step(TEST), step(scratch)))
        for piped in (
            "grep -rl foo src | xargs sed -i 's/foo/bar/g'",
            "grep -rl foo src | while read f; do sed -i 's/foo/bar/' \"$f\"; done",
        ):
            self.assertFalse(proved(step(FIX), step(TEST), step(bash(piped))), piped)

    def test_an_in_place_edit_on_a_loop_or_assigned_variable_counts_by_its_value(self):
        for scratch in (
            "for f in /tmp/rv/*.js; do sed -i 's/x/y/' \"$f\"; done",
            "d=$(mktemp -d); sed -i 's/x/y/' $d/cart.js",
        ):
            self.assertTrue(proved(step(FIX), step(TEST), step(bash(scratch))), scratch)
        for edit_cmd in ("for f in src/cart.js; do sed -i 's/x/y/' \"$f\"; done", "f=src/cart.js; sed -i 's/x/y/' $f"):
            self.assertFalse(proved(step(FIX), step(TEST), step(bash(edit_cmd))), edit_cmd)

    def test_an_in_place_edit_on_a_command_substitution_counts_in_the_current_directory(self):
        scratch = bash("cd /tmp/rv && sed -i 's/old/new/g' $(grep -rl old src)")
        self.assertTrue(proved(step(FIX), step(TEST), step(scratch)))
        self.assertFalse(proved(step(FIX), step(TEST), step(bash("sed -i 's/old/new/g' $(grep -rl old src)"))))

    def test_a_write_to_a_function_argument_counts_in_the_current_directory(self):
        mutate = "mutate() {\n  python3 -c \"p='$1'; open(p,'w').write('x')\"\n}\nmutate src/cart.js"
        self.assertTrue(proved(step(FIX), step(TEST), step(bash("cd /tmp/rv\n" + mutate))))
        self.assertFalse(proved(step(FIX), step(TEST), step(bash(mutate))))

    def test_an_in_place_edit_continued_over_lines_counts_by_its_file_operand(self):
        scratch = bash("sed -i \\\n  -e 's/a/b/' \\\n  /tmp/cart.js")
        self.assertTrue(proved(step(FIX), step(TEST), step(scratch)))
        continued = bash("sed -i \\\n  -e 's/a/b/' \\\n  src/cart.js")
        self.assertFalse(proved(step(FIX), step(TEST), step(continued)))

    def test_a_copy_or_patch_into_app_is_an_edit_outside_a_test_run(self):
        copy_out = bash("cp /app/src/cart.js /tmp/cart.bak")
        self.assertTrue(proved(step(FIX), step(TEST), step(copy_out)))
        for staged in ("cp /tmp/cart.js /app/src/cart.js", "mv /tmp/cart.js src/cart.js", "git apply /tmp/fix.patch"):
            self.assertFalse(proved(step(FIX), step(TEST), step(write("/tmp/cart.js")), step(bash(staged))), staged)


class MutationRunTests(unittest.TestCase):
    def test_mutate_test_restore_in_one_command_is_not_the_last_edit(self):
        mutation = bash(
            "cp src/cart.js /tmp/cart.bak && sed -i 's/>=/>/' src/cart.js && npm test | grep fail; "
            "cp /tmp/cart.bak src/cart.js"
        )
        self.assertTrue(proved(step(FIX), step(TEST), step(mutation)))
        self.assertFalse(proved(step(FIX), step(TEST), step(bash("sed -i 's/>=/>/' src/cart.js; git diff"))))

    def test_a_test_run_inside_a_shell_function_counts_where_the_function_is_called(self):
        define = "cp src/cart.js /tmp/cart.bak\nrun() { node --test 2>&1 | grep fail; cp /tmp/cart.bak src/cart.js; }\n"
        mutate = "sed -i 's/>=/>/' src/cart.js"
        for call in ("run \"boundary\"", "echo \"[$(run)]\""):
            self.assertTrue(proved(step(FIX), step(TEST), step(bash(f"{define}{mutate}; {call}"))), call)
        self.assertFalse(proved(step(FIX), step(TEST), step(bash(f"{define}run; {mutate}"))))

    def test_an_edit_after_the_commands_last_test_run_is_unproven(self):
        self.assertTrue(proved(step(FIX), step(TEST), step(bash("sed -i 's/>=/>/' src/cart.js && npm test"))))
        for late in ("npm test; sed -i 's/>=/>/' src/cart.js", "npm test; echo 'bad' > src/cart.js"):
            self.assertFalse(proved(step(FIX), step(TEST), step(bash(late))), late)


class TestCommandTests(unittest.TestCase):
    def test_node_test_counts_with_or_without_paths(self):
        self.assertTrue(proved(step(FIX), step(bash("node --test"))))
        self.assertTrue(proved(step(FIX), step(bash("node --test-reporter=spec --test test/cart.test.js"))))
        self.assertFalse(proved(step(FIX), step(bash("node --test-name-pattern=cart scripts/seed.js"))))

    def test_npm_run_with_flags_counts(self):
        self.assertTrue(proved(step(FIX), step(bash("npm run -s check"))))
        self.assertFalse(proved(step(FIX), step(bash("npm run -s build"))))

    def test_the_task_visible_test_cmd_counts(self):
        self.assertTrue(proved(step(FIX), step(bash("make check")), visible_test_cmd="make check"))
        self.assertFalse(proved(step(FIX), step(bash("make check"))))

    def test_a_quoted_test_command_is_not_a_run(self):
        self.assertFalse(proved(step(FIX), step(bash("ps aux | grep -E 'node --test|psql'"))))

    def test_a_test_command_run_by_sh_c_or_bash_lc_counts(self):
        self.assertTrue(proved(step(FIX), step(bash("sh -c 'npm test'"))))
        self.assertTrue(proved(step(FIX), step(bash('bash -lc "cd /app && npm test"'))))
        self.assertFalse(proved(step(FIX), step(bash("sh -c 'npm run build'"))))


if __name__ == "__main__":
    unittest.main()
