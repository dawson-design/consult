"""A local page for labelling a judge_labels.py sheet in the browser.

  uv run scripts/judge_labels.py serve <sheet.csv> [--port 8765] [--no-browser]

It serves the blind sheet and its case files on 127.0.0.1 only, and writes
each answer straight into the sheet, so labelling can stop and resume at any
point. It never reads the key file, so it cannot show the judge's answer, its
reason, or the arm. Every API call carries a random token from the page URL,
so another site open in the browser cannot write labels. Standard library
only; judge_labels.py holds the sheet format.
"""

from __future__ import annotations

import csv
import json
import os
import re
import secrets
import webbrowser
from functools import partial
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import urlparse

CASE_RE = re.compile(r"^c\d{3}$")
ANSWERS = ("yes", "no", "")
SHOWN = ("row", "case", "task", "dimension", "item", "question", "look_at", "yes_when", "no_when", "human", "note")


def read_rows(sheet: Path) -> tuple[list[str], list[dict]]:
    """The sheet's header and rows; utf-8-sig, since a spreadsheet save may add a byte-order mark."""
    with sheet.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), list(reader)


def page_rows(sheet: Path) -> list[dict]:
    """The rows the page shows, grouped by case so each case is read once, without the tier."""
    _, rows = read_rows(sheet)
    return sorted(({k: row.get(k, "") for k in SHOWN} for row in rows), key=lambda r: (r["case"], r["row"]))


def write_label(sheet: Path, row_id: str, human: str, note: str) -> str | None:
    """Set one row's human label and note; returns an error message, or None when saved.

    The sheet is rewritten to a temporary file and moved into place, so a crash
    mid-write cannot leave a half-written sheet.
    """
    if human not in ANSWERS:
        return f"human must be yes, no, or empty, got {human!r}"
    header, rows = read_rows(sheet)
    target = next((row for row in rows if row.get("row") == row_id), None)
    if target is None:
        return f"no row {row_id!r} in the sheet"
    target["human"], target["note"] = human, note
    staged = sheet.with_name(f".{sheet.name}.saving")
    with staged.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=header)
        writer.writeheader()
        writer.writerows(rows)
    os.replace(staged, sheet)
    return None


def case_text(cases: Path, case: str) -> str | None:
    """One case file's text, or None for an id that is not a case (so no other path can be read)."""
    if not CASE_RE.match(case):
        return None
    path = cases / f"{case}.md"
    return path.read_text(encoding="utf-8") if path.is_file() else None


class LabelHandler(BaseHTTPRequestHandler):
    """GET / (the page), GET /api/rows, GET /api/case/<id>, POST /api/label."""

    def __init__(self, *args, sheet: Path, cases: Path, token: str, **kwargs) -> None:
        self.sheet, self.cases, self.token = sheet, cases, token
        super().__init__(*args, **kwargs)

    def log_message(self, format: str, *args) -> None:
        return

    def send(self, status: HTTPStatus, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def send_json(self, status: HTTPStatus, value: object) -> None:
        self.send(status, json.dumps(value).encode(), "application/json")

    def authorized(self) -> bool:
        if secrets.compare_digest(self.headers.get("X-Label-Token", ""), self.token):
            return True
        self.send_json(HTTPStatus.FORBIDDEN, {"error": "missing or wrong token; open the URL the server printed"})
        return False

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path == "/":
            self.send(HTTPStatus.OK, PAGE.encode(), "text/html; charset=utf-8")
        elif path == "/api/rows" and self.authorized():
            self.send_json(HTTPStatus.OK, page_rows(self.sheet))
        elif path.startswith("/api/case/") and self.authorized():
            text = case_text(self.cases, path.removeprefix("/api/case/"))
            if text is None:
                self.send_json(HTTPStatus.NOT_FOUND, {"error": "no such case"})
            else:
                self.send(HTTPStatus.OK, text.encode(), "text/plain; charset=utf-8")
        elif not path.startswith("/api/"):
            self.send_json(HTTPStatus.NOT_FOUND, {"error": "not found"})

    def do_POST(self) -> None:
        if urlparse(self.path).path != "/api/label":
            self.send_json(HTTPStatus.NOT_FOUND, {"error": "not found"})
            return
        if not self.authorized():
            return
        try:
            body = json.loads(self.rfile.read(int(self.headers.get("Content-Length") or 0)))
            error = write_label(self.sheet, str(body["row"]), str(body["human"]), str(body.get("note") or ""))
        except (ValueError, KeyError, TypeError):
            error = "the body must be JSON with row and human"
        if error:
            self.send_json(HTTPStatus.BAD_REQUEST, {"error": error})
        else:
            self.send_json(HTTPStatus.OK, {"saved": True})


def serve(sheet: Path, cases: Path, port: int, open_browser: bool) -> int:
    """Serve the page until interrupted; prints the URL with its token."""
    if not sheet.is_file() or not cases.is_dir():
        print(f"{sheet} or {cases} is missing; export a sheet with judge_labels.py export first")
        return 2
    token = secrets.token_urlsafe(16)
    handler = partial(LabelHandler, sheet=sheet.resolve(), cases=cases.resolve(), token=token)
    server = HTTPServer(("127.0.0.1", port), handler)
    url = f"http://127.0.0.1:{server.server_address[1]}/#t={token}"
    print(f"Labelling {sheet.name}: {url}\nAnswers save to the sheet as you go. Press Ctrl+C to stop.", flush=True)
    if open_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


PAGE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Judge labels</title>
<style>
:root {
  --bg: #ffffff; --surface: #f4f4f4; --text: #161616; --muted: #525252; --border: #c6c6c6;
  --accent: #0f62fe; --accent-text: #ffffff; --focus: #0f62fe;
  --add-bg: #defbe6; --add-text: #044317; --del-bg: #fff1f1; --del-text: #750e13; --heading: #161616;
  --error: #da1e28;
  --space-1: 4px; --space-2: 8px; --space-3: 12px; --space-4: 16px; --space-5: 24px;
  --radius: 4px; --mono: ui-monospace, SFMono-Regular, Menlo, monospace;
  --sans: system-ui, -apple-system, "Segoe UI", sans-serif;
}
@media (prefers-color-scheme: dark) {
  :root {
    --bg: #161616; --surface: #262626; --text: #f4f4f4; --muted: #c6c6c6; --border: #525252;
    --accent: #78a9ff; --accent-text: #161616; --focus: #ffffff;
    --add-bg: #044317; --add-text: #defbe6; --del-bg: #520408; --del-text: #ffd7d9; --heading: #ffffff;
    --error: #ff8389;
  }
}
* { box-sizing: border-box; }
body { margin: 0; background: var(--bg); color: var(--text); font: 15px/1.5 var(--sans); }
main { display: grid; grid-template-columns: minmax(320px, 420px) 1fr; height: 100vh; }
@media (max-width: 860px) { main { grid-template-columns: 1fr; height: auto; } }
#item { padding: var(--space-5); border-right: 1px solid var(--border); overflow-y: auto; }
#case { overflow-y: auto; padding: var(--space-4) var(--space-5); }
h1 { font-size: 13px; font-weight: 600; color: var(--muted); margin: 0 0 var(--space-2); }
h2 { font-size: 20px; line-height: 1.3; margin: 0 0 var(--space-4); }
dl { margin: 0 0 var(--space-5); }
dt { font-size: 13px; font-weight: 600; color: var(--muted); margin-top: var(--space-3); }
dd { margin: var(--space-1) 0 0; }
.answers { display: flex; gap: var(--space-2); margin-bottom: var(--space-3); }
button { font: inherit; padding: var(--space-2) var(--space-4); border-radius: var(--radius);
  border: 1px solid var(--border); background: var(--surface); color: var(--text); cursor: pointer; }
button.primary { background: var(--accent); color: var(--accent-text); border-color: var(--accent); font-weight: 600; }
button[aria-pressed="true"] { outline: 2px solid var(--text); outline-offset: 2px; }
button:focus-visible, textarea:focus-visible { outline: 2px solid var(--focus); outline-offset: 2px; }
@media (forced-colors: active) { button:focus-visible, textarea:focus-visible { outline: 2px solid transparent; } }
label { display: block; font-size: 13px; font-weight: 600; color: var(--muted); margin: var(--space-4) 0 var(--space-1); }
textarea { width: 100%; min-height: 64px; font: inherit; padding: var(--space-2); border-radius: var(--radius);
  border: 1px solid var(--border); background: var(--bg); color: var(--text); }
.nav { display: flex; gap: var(--space-2); flex-wrap: wrap; margin-top: var(--space-4); }
.status { min-height: 1.5em; margin-top: var(--space-3); color: var(--muted); }
.status.error { color: var(--error); font-weight: 600; }
.progress { color: var(--muted); font-size: 13px; }
.keys { color: var(--muted); font-size: 13px; margin-top: var(--space-5); }
kbd { font-family: var(--mono); border: 1px solid var(--border); border-radius: var(--radius); padding: 0 var(--space-1); }
pre { margin: 0; font: 13px/1.45 var(--mono); white-space: pre-wrap; overflow-wrap: anywhere; }
pre span { display: block; }
.add { background: var(--add-bg); color: var(--add-text); }
.del { background: var(--del-bg); color: var(--del-text); }
.head { color: var(--heading); font-weight: 700; }
</style>
</head>
<body>
<main>
  <section id="item" aria-labelledby="question">
    <p class="progress" id="progress">Loading the sheet…</p>
    <h1 id="where"></h1>
    <h2 id="question"></h2>
    <dl>
      <dt>Where to look</dt><dd id="look_at"></dd>
      <dt>Answer yes when</dt><dd id="yes_when"></dd>
      <dt>Answer no when</dt><dd id="no_when"></dd>
    </dl>
    <div class="answers" role="group" aria-label="Your answer">
      <button type="button" class="primary" data-answer="yes">Yes</button>
      <button type="button" class="primary" data-answer="no">No</button>
      <button type="button" data-answer="">Can't tell</button>
    </div>
    <p id="current">Not labelled yet.</p>
    <label for="note">Note (optional, saved with your answer)</label>
    <textarea id="note"></textarea>
    <div class="nav">
      <button type="button" id="prev">Previous</button>
      <button type="button" id="next">Next</button>
      <button type="button" id="unlabelled">Next unlabelled</button>
    </div>
    <p class="status" id="status" role="status" aria-live="polite"></p>
    <p class="keys"><kbd>y</kbd> yes, <kbd>n</kbd> no, <kbd>s</kbd> can't tell, <kbd>j</kbd>/<kbd>k</kbd> next/previous.
      Keys are off while you type a note. Yes means the requirement is met. For a report item, the report is
      everything the agent told the user across its replies; the later reply stands where two conflict.</p>
  </section>
  <section id="case" aria-label="Case"><pre id="case-text">Loading…</pre></section>
</main>
<script>
const token = new URLSearchParams(location.hash.slice(1)).get("t") || "";
let rows = [], index = 0, shownCase = null;
const $ = (id) => document.getElementById(id);

async function api(path, options = {}) {
  const response = await fetch(path, { ...options, headers: { "X-Label-Token": token, ...(options.headers || {}) } });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body.error || `request failed (${response.status})`);
  }
  return response;
}

function setStatus(text, isError = false) {
  $("status").textContent = text;
  $("status").className = isError ? "status error" : "status";
}

function renderCase(text) {
  const pre = $("case-text");
  pre.replaceChildren();
  let inDiff = false;
  for (const line of text.split("\n")) {
    const span = document.createElement("span");
    span.textContent = line || " ";
    if (line.startsWith("```")) inDiff = line.startsWith("```diff");
    else if (inDiff && line.startsWith("+") && !line.startsWith("+++")) span.className = "add";
    else if (inDiff && line.startsWith("-") && !line.startsWith("---")) span.className = "del";
    else if (!inDiff && /^#{1,3} /.test(line)) span.className = "head";
    pre.append(span);
  }
}

async function show(i) {
  if (!rows.length) return;
  index = Math.max(0, Math.min(rows.length - 1, i));
  const row = rows[index];
  const done = rows.filter((r) => r.human).length;
  $("progress").textContent = `Item ${index + 1} of ${rows.length} · ${done} labelled`;
  $("where").textContent = `Case ${row.case} · ${row.task} · ${row.dimension} · ${row.item}`;
  for (const key of ["question", "look_at", "yes_when", "no_when"]) $(key).textContent = row[key];
  $("note").value = row.note || "";
  $("current").textContent = row.human ? `Your answer: ${row.human}.` : "Not labelled yet.";
  for (const button of document.querySelectorAll("[data-answer]")) {
    button.setAttribute("aria-pressed", String(row.human !== "" && button.dataset.answer === row.human));
  }
  if (row.case !== shownCase) {
    $("case-text").textContent = "Loading the case…";
    try {
      renderCase(await (await api(`/api/case/${row.case}`)).text());
      shownCase = row.case;
      $("case").scrollTop = 0;
    } catch (error) {
      $("case-text").textContent = `Could not load case ${row.case}: ${error.message}`;
    }
  }
}

async function answer(value) {
  const row = rows[index];
  const note = $("note").value;
  setStatus("Saving…");
  try {
    await api("/api/label", { method: "POST", body: JSON.stringify({ row: row.row, human: value, note }) });
    row.human = value; row.note = note;
    setStatus(value ? `Saved ${row.row}: ${value}.` : `Saved ${row.row}: can't tell (left unlabelled).`);
    const next = rows.findIndex((r, i) => i > index && !r.human);
    if (next === -1 && rows.every((r) => r.human)) {
      await show(index);
      setStatus("Every item is labelled. Run judge_labels.py agree on the sheet.");
    } else {
      await show(value ? (next === -1 ? index + 1 : next) : index + 1);
    }
  } catch (error) {
    setStatus(`Not saved: ${error.message}. Is the server still running?`, true);
  }
}

document.querySelectorAll("[data-answer]").forEach((b) => b.addEventListener("click", () => answer(b.dataset.answer)));
$("prev").addEventListener("click", () => show(index - 1));
$("next").addEventListener("click", () => show(index + 1));
$("unlabelled").addEventListener("click", () => {
  const next = rows.findIndex((r, i) => i > index && !r.human);
  const first = rows.findIndex((r) => !r.human);
  if (next !== -1 || first !== -1) show(next !== -1 ? next : first);
  else setStatus("Every item is labelled.");
});
document.addEventListener("keydown", (event) => {
  if (event.target.tagName === "TEXTAREA" || event.metaKey || event.ctrlKey || event.altKey) return;
  const actions = { y: () => answer("yes"), n: () => answer("no"), s: () => answer(""), j: () => show(index + 1), k: () => show(index - 1) };
  if (actions[event.key]) { event.preventDefault(); actions[event.key](); }
});

(async () => {
  try {
    rows = await (await api("/api/rows")).json();
    if (!rows.length) { $("progress").textContent = "The sheet has no rows."; return; }
    const first = rows.findIndex((r) => !r.human);
    await show(first === -1 ? 0 : first);
  } catch (error) {
    $("progress").textContent = `Could not load the sheet: ${error.message}`;
    $("case-text").textContent = "";
  }
})();
</script>
</body>
</html>
"""
