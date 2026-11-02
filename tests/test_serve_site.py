"""The local site server's pure parts: change classification and reload-client injection.

The HTTP handler itself is exercised by running the server; these tests pin the decisions
that pick between a stylesheet swap and a full reload, and where the client lands in a page.
"""

from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path

from helpers import ROOT

SPEC = importlib.util.spec_from_file_location("serve_site", ROOT / "scripts/serve_site.py")
serve_site = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(serve_site)


class ChangeKindTest(unittest.TestCase):
    """change_kind picks no event, a stylesheet swap, or a reload."""

    def test_no_change_sends_nothing(self) -> None:
        snap = {Path("a.html"): 1.0}
        self.assertIsNone(serve_site.change_kind(snap, dict(snap)))

    def test_only_stylesheets_changed_swaps_css(self) -> None:
        before = {Path("a.css"): 1.0, Path("b.html"): 1.0}
        after = {Path("a.css"): 2.0, Path("b.html"): 1.0, Path("c.css"): 1.0}
        self.assertEqual(serve_site.change_kind(before, after), "css")

    def test_any_other_change_reloads(self) -> None:
        before = {Path("a.css"): 1.0, Path("w.js"): 1.0}
        after = {Path("a.css"): 2.0, Path("w.js"): 2.0}
        self.assertEqual(serve_site.change_kind(before, after), "reload")

    def test_removed_file_reloads(self) -> None:
        self.assertEqual(serve_site.change_kind({Path("w.js"): 1.0}, {}), "reload")


class InjectTest(unittest.TestCase):
    """inject places the client before the last </body>, or appends it."""

    def test_before_closing_body(self) -> None:
        out = serve_site.inject(b"<html><body><p>x</p></BODY></html>")
        self.assertTrue(out.endswith(serve_site.CLIENT.encode() + b"</BODY></html>"))

    def test_appends_without_body(self) -> None:
        self.assertEqual(serve_site.inject(b"<p>x</p>"), b"<p>x</p>" + serve_site.CLIENT.encode())

    def test_non_utf8_page_passes_through(self) -> None:
        out = serve_site.inject("<body>caf\xe9</body>".encode("latin-1"))
        self.assertIn("caf\xe9".encode("latin-1"), out)


class SnapshotTest(unittest.TestCase):
    """snapshot lists files under the root and skips hidden paths."""

    def test_skips_hidden(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "index.html").write_text("x")
            (root / ".git").mkdir()
            (root / ".git" / "HEAD").write_text("x")
            self.assertEqual(set(serve_site.snapshot(root)), {root / "index.html"})


if __name__ == "__main__":
    unittest.main()
