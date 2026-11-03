"""The local labelling page: it saves answers into the sheet, stays blind, and refuses calls without its token.

  python3 -m unittest discover eval/verifier/tests

The server runs on a free port in a thread against a fixture sheet.
"""

from __future__ import annotations

import csv
import json
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from functools import partial
from http.server import HTTPServer
from pathlib import Path

EVAL_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(EVAL_DIR / "scripts"))

import judge_labels as jl
import label_page as lp

TOKEN = "test-token"


def write_sheet(path: Path) -> None:
    rows = [
        {"row": "r002", "case": "c002", "task": "t", "dimension": "scope", "item": "scope.a", "tier": "must"},
        {"row": "r001", "case": "c001", "task": "t", "dimension": "proof", "item": "proof.a", "tier": "quality"},
        {"row": "r003", "case": "c001", "task": "t", "dimension": "report", "item": "report.a", "tier": "must"},
    ]
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=jl.COLUMNS)
        writer.writeheader()
        for row in rows:
            writer.writerow({**dict.fromkeys(jl.COLUMNS, ""), **row, "question": f"Is {row['item']} met?"})


class LabelPageTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        root = Path(self._tmp.name)
        self.sheet = root / "labels.csv"
        write_sheet(self.sheet)
        self.cases = jl.cases_dir(self.sheet)
        self.cases.mkdir()
        (self.cases / "c001.md").write_text("# Case c001\n\n```diff\n+added\n```\n")
        (root / "secret.md").write_text("not a case")
        # A key file beside the sheet holds the judge's answers; the page must never serve it.
        jl.key_path(self.sheet).write_text(json.dumps({"rows": {"r001": {"answer": "JUDGE-ANSWER", "arm": "consult"}}}))
        handler = partial(lp.LabelHandler, sheet=self.sheet, cases=self.cases, token=TOKEN)
        self.server = HTTPServer(("127.0.0.1", 0), handler)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
        self.base = f"http://127.0.0.1:{self.server.server_address[1]}"

    def request(self, path: str, body: dict | None = None, token: str = TOKEN) -> tuple[int, bytes]:
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(self.base + path, data=data, headers={"X-Label-Token": token})
        try:
            with urllib.request.urlopen(req) as response:
                return response.status, response.read()
        except urllib.error.HTTPError as error:
            return error.code, error.read()

    def labels(self) -> dict[str, tuple[str, str]]:
        _, rows = lp.read_rows(self.sheet)
        return {r["row"]: (r["human"], r["note"]) for r in rows}

    def test_the_page_loads_without_a_token(self):
        status, body = self.request("/", token="")
        self.assertEqual(status, 200)
        self.assertIn(b"<title>Judge labels</title>", body)

    def test_rows_come_grouped_by_case_without_the_tier(self):
        status, body = self.request("/api/rows")
        rows = json.loads(body)
        self.assertEqual(status, 200)
        self.assertEqual([r["row"] for r in rows], ["r001", "r003", "r002"])
        self.assertNotIn("tier", rows[0])

    def test_nothing_the_page_serves_reveals_the_judges_answer_or_the_arm(self):
        served = b"".join(self.request(p)[1] for p in ("/", "/api/rows", "/api/case/c001"))
        self.assertNotIn(b"JUDGE-ANSWER", served)
        self.assertNotIn(b"consult", served.lower())

    def test_an_answer_and_note_save_into_the_sheet(self):
        status, _ = self.request("/api/label", {"row": "r003", "human": "no", "note": "claims a test it never ran"})
        self.assertEqual(status, 200)
        self.assertEqual(self.labels()["r003"], ("no", "claims a test it never ran"))
        self.assertEqual(self.labels()["r001"], ("", ""))

    def test_cant_tell_clears_an_earlier_answer(self):
        self.request("/api/label", {"row": "r001", "human": "yes"})
        self.request("/api/label", {"row": "r001", "human": ""})
        self.assertEqual(self.labels()["r001"], ("", ""))

    def test_a_label_other_than_yes_no_or_empty_is_refused(self):
        status, body = self.request("/api/label", {"row": "r001", "human": "maybe"})
        self.assertEqual(status, 400)
        self.assertIn(b"yes, no, or empty", body)
        self.assertEqual(self.labels()["r001"], ("", ""))

    def test_an_unknown_row_is_refused(self):
        self.assertEqual(self.request("/api/label", {"row": "r999", "human": "yes"})[0], 400)

    def test_calls_without_the_token_are_refused(self):
        self.assertEqual(self.request("/api/rows", token="wrong")[0], 403)
        self.assertEqual(self.request("/api/label", {"row": "r001", "human": "yes"}, token="")[0], 403)
        self.assertEqual(self.labels()["r001"], ("", ""))

    def test_only_case_files_can_be_read(self):
        self.assertEqual(self.request("/api/case/c001")[0], 200)
        for path in ("/api/case/..%2Fsecret", "/api/case/secret", "/api/case/c999"):
            with self.subTest(path=path):
                self.assertEqual(self.request(path)[0], 404)

    def test_a_sheet_with_a_byte_order_mark_keeps_its_header(self):
        self.sheet.write_bytes(b"\xef\xbb\xbf" + self.sheet.read_bytes())
        self.request("/api/label", {"row": "r001", "human": "yes"})
        self.assertEqual(lp.read_rows(self.sheet)[0][0], "row")
        self.assertEqual(self.labels()["r001"], ("yes", ""))


if __name__ == "__main__":
    unittest.main()
