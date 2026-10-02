"""Passing and failing workspaces for the hidden checks in eval/verifier/hidden/.

  python3 -m unittest discover eval/verifier/tests

Each task's passing workspace lives in fixtures/hidden/<task>/. A failing
workspace is that fixture with one edit that makes the work genuinely wrong.
Checks run the way consult_lib.hidden_check_passes runs them: the script is
passed to `node --input-type=module -e` with the workspace as the working
directory. Needs Node 22 or later on PATH.
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

HIDDEN = Path(__file__).resolve().parents[1] / "hidden"
FIXTURES = Path(__file__).resolve().parent / "fixtures" / "hidden"

# (path, old, new) replacements applied to a copy of the passing fixture.
Edit = tuple[str, str, str]


class HiddenCheckCase(unittest.TestCase):
    task = ""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)

    def run_check(self, *edits: Edit) -> subprocess.CompletedProcess[str]:
        workspace = Path(self._tmp.name) / self.task
        shutil.copytree(FIXTURES / self.task, workspace)
        for path, old, new in edits:
            text = (workspace / path).read_text()
            self.assertIn(old, text, f"fixture edit does not apply to {path}")
            (workspace / path).write_text(text.replace(old, new))
        script = (HIDDEN / f"{self.task}.mjs").read_text()
        return subprocess.run(
            ["node", "--input-type=module", "-e", script],
            cwd=workspace, capture_output=True, text=True, timeout=120,
        )

    def assertPasses(self, *edits: Edit) -> None:
        result = self.run_check(*edits)
        self.assertEqual(result.returncode, 0, result.stderr[-1500:])

    def assertFails(self, *edits: Edit, reason: str) -> None:
        result = self.run_check(*edits)
        self.assertNotEqual(result.returncode, 0, "check passed a wrong implementation")
        self.assertIn(reason, result.stderr)


class AccessibleUiStateTests(HiddenCheckCase):
    task = "accessible-ui-state"
    STATUS = '<p id="status" role="status"></p>'

    def test_role_status_region_passes(self) -> None:
        self.assertPasses()

    def test_output_element_passes_as_an_implicit_polite_region(self) -> None:
        self.assertPasses(("public/index.html", self.STATUS, '<output id="status"></output>'))

    def test_assertive_live_region_fails(self) -> None:
        self.assertFails(
            ("public/index.html", self.STATUS, '<p id="status" role="alert"></p>'),
            reason="status region is announced politely",
        )

    def test_polite_ancestor_of_status_passes(self) -> None:
        self.assertPasses(("public/index.html", self.STATUS, '<div aria-live="polite"><p id="status"></p></div>'))

    def test_renamed_polite_region_passes(self) -> None:
        self.assertPasses(
            ("public/index.html", self.STATUS, '<p id="message" role="status"></p>'),
            ("public/index.html", 'getElementById("status")', 'getElementById("message")'),
        )

    def test_plain_status_beside_an_unrelated_polite_region_fails(self) -> None:
        self.assertFails(
            ("public/index.html", self.STATUS, '<p id="status"></p>\n<output name="count" hidden></output>'),
            reason="status region is announced politely",
        )

    def test_commented_out_polite_status_fails(self) -> None:
        self.assertFails(
            ("public/index.html", self.STATUS, f'<!-- {self.STATUS} -->\n<p id="status"></p>'),
            reason="status region is announced politely",
        )


class ApiErrorContractTests(HiddenCheckCase):
    task = "api-error-contract"
    FLAT = "body: { code, message }"

    def test_flat_code_and_message_passes(self) -> None:
        self.assertPasses()

    def test_nested_error_object_passes(self) -> None:
        self.assertPasses(("src/users.js", self.FLAT, "body: { error: { code, message } }"))

    def test_problem_details_passes(self) -> None:
        self.assertPasses(("src/users.js", self.FLAT, 'body: { type: code, title: message, status }'))

    def test_ok_for_a_missing_id_fails(self) -> None:
        self.assertFails(
            ("src/users.js", "failure(400, ", "failure(200, "),
            reason="missing id: status",
        )

    def test_same_code_for_both_errors_fails(self) -> None:
        self.assertFails(
            ("src/users.js", '"user_not_found"', '"missing_user_id"'),
            reason="need different machine-readable codes",
        )


class DatabaseReleaseSafetyTests(HiddenCheckCase):
    task = "database-release-safety"
    INDEX = "migrations/002_customer_email_unique_index.sql"
    BUILD = "CREATE UNIQUE INDEX CONCURRENTLY IF NOT EXISTS customers_email_idx ON customers (email);"
    COLUMN = "ALTER TABLE customers ADD COLUMN email text;"
    LOWER = "customers_email_lower CHECK (email = lower(email))"
    DOCS = "docs/customer-email-rollout.md"
    VALIDATE = "Validate that `customers_email_idx` is valid before running 003."

    def test_online_migration_with_rollback_dir_and_docs_passes(self) -> None:
        self.assertPasses()

    def test_blocking_unique_index_fails(self) -> None:
        self.assertFails(
            (self.INDEX, "UNIQUE INDEX CONCURRENTLY", "UNIQUE INDEX"),
            reason="no non-concurrent index build on an existing table",
        )

    def test_concurrent_build_inside_a_transaction_fails(self) -> None:
        self.assertFails(
            (self.INDEX, self.BUILD, f"BEGIN;\n{self.BUILD}\nCOMMIT;"),
            reason="does not run CONCURRENTLY inside a transaction block",
        )

    def test_unique_constraint_that_builds_its_own_index_fails(self) -> None:
        self.assertFails(
            ("migrations/003_customer_email_unique_constraint.sql", "UNIQUE USING INDEX customers_email_idx", "UNIQUE (email)"),
            reason="no UNIQUE or PRIMARY KEY constraint that builds its own index",
        )

    def test_not_null_column_with_a_default_passes(self) -> None:
        self.assertPasses(self.after_column("ALTER TABLE customers ADD COLUMN email_verified boolean NOT NULL DEFAULT false;"))

    def test_not_null_column_without_a_default_fails(self) -> None:
        self.assertFails(
            self.after_column("ALTER TABLE customers ADD COLUMN email_verified boolean NOT NULL;"),
            reason="no NOT NULL column added without a default",
        )

    def test_check_constraint_added_not_valid_then_validated_passes(self) -> None:
        self.assertPasses(self.after_column(
            f"ALTER TABLE customers ADD CONSTRAINT {self.LOWER} NOT VALID;\n"
            "ALTER TABLE customers VALIDATE CONSTRAINT customers_email_lower;"
        ))

    def test_check_constraint_validated_under_lock_fails(self) -> None:
        self.assertFails(
            self.after_column(f"ALTER TABLE customers ADD CONSTRAINT {self.LOWER};"),
            reason="no CHECK or FOREIGN KEY constraint added without NOT VALID",
        )

    def test_foreign_key_validated_under_lock_fails(self) -> None:
        self.assertFails(
            self.after_column("ALTER TABLE customers ADD CONSTRAINT customers_org_fk FOREIGN KEY (org_id) REFERENCES orgs (id);"),
            reason="no CHECK or FOREIGN KEY constraint added without NOT VALID",
        )

    def test_column_type_change_fails(self) -> None:
        self.assertFails(
            self.after_column("ALTER TABLE customers ALTER COLUMN email TYPE text USING lower(email);"),
            reason="no column type change",
        )

    def test_lock_that_allows_writes_passes(self) -> None:
        self.assertPasses(self.after_column("LOCK TABLE customers IN SHARE UPDATE EXCLUSIVE MODE;"))

    def test_lock_that_blocks_writes_fails(self) -> None:
        self.assertFails(
            self.after_column("LOCK TABLE customers IN ACCESS EXCLUSIVE MODE;"),
            reason="no LOCK TABLE in a mode that blocks writes",
        )

    def test_concurrent_reindex_passes(self) -> None:
        self.assertPasses((self.INDEX, self.BUILD, f"{self.BUILD}\nREINDEX INDEX CONCURRENTLY customers_email_idx;"))

    def test_blocking_reindex_fails(self) -> None:
        self.assertFails(
            (self.INDEX, self.BUILD, f"{self.BUILD}\nREINDEX TABLE customers;"),
            reason="no non-concurrent REINDEX",
        )

    def test_validation_notes_under_the_instruction_wording_pass(self) -> None:
        self.assertPasses((self.DOCS, self.VALIDATE, "## Validation\n\nConfirm `customers_email_idx` has `indisvalid = true` before running 003."))

    def test_notes_without_validation_fail(self) -> None:
        self.assertFails((self.DOCS, self.VALIDATE, ""), reason="documents validation")

    def after_column(self, statements: str) -> Edit:
        return ("migrations/001_customer_email.sql", self.COLUMN, f"{self.COLUMN}\n{statements}")


class SecurityBoundaryFixTests(HiddenCheckCase):
    task = "security-boundary-fix"
    ORIGIN_CHECK = "return url.origin === TRUSTED_ORIGIN && !url.username && !url.password ? target : \"/\";"

    def test_trusted_host_named_only_in_the_workspace_passes(self) -> None:
        self.assertPasses()

    def test_open_redirect_to_an_external_host_fails(self) -> None:
        self.assertFails(
            ("src/redirect.js", self.ORIGIN_CHECK, "return target;"),
            reason="https://evil.example/phish",
        )

    def test_prefix_match_on_the_trusted_host_fails(self) -> None:
        self.assertFails(
            ("src/redirect.js", self.ORIGIN_CHECK, 'return target.startsWith(TRUSTED_ORIGIN) ? target : "/";'),
            reason="is not the trusted HTTPS host app.example.com",
        )

    def test_suffix_match_on_the_trusted_host_fails(self) -> None:
        suffix = 'return url.protocol === "https:" && url.hostname.endsWith("example.com") && !url.username ? target : "/";'
        self.assertFails(
            ("src/redirect.js", self.ORIGIN_CHECK, suffix),
            reason="https://evilapp.example.com/x is not the trusted HTTPS host",
        )

    def test_backslash_protocol_relative_target_fails(self) -> None:
        self.assertFails(
            ("src/redirect.js", "/[\\s\\\\]/", "/\\s/"),
            reason="/\\evil.example/phish",
        )


class ServiceFromBriefTests(HiddenCheckCase):
    task = "service-from-brief"

    def test_short_links_printed_on_localhost_pass(self) -> None:
        self.assertPasses()

    def test_short_link_that_does_not_redirect_fails(self) -> None:
        self.assertFails(
            ("server.js", "res.writeHead(302, { location: link.target }).end();", "res.writeHead(404).end();"),
            reason="produced a working short link",
        )


if __name__ == "__main__":
    unittest.main()
