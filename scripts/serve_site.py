#!/usr/bin/env python3
"""Serve the marketing site in `site/` locally, reloading the browser when a file changes.

`site/` is plain static HTML, CSS, and JavaScript, so GitHub Pages can publish it as is. This
server adds live reload only at serve time: it injects a small script into each HTML response
that listens on an event stream. A change to a stylesheet swaps the stylesheets in place; any
other change reloads the page. Standard library only, like the rest of `scripts/`.

Usage: python3 scripts/serve_site.py [--port 8000] [--root site]
"""

from __future__ import annotations

import argparse
import functools
import http.server
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
RELOAD_PATH = "/__reload"
POLL_SECONDS = 0.25
PING_SECONDS = 5.0  # a comment line this often lets a closed tab end its stream promptly
DISCONNECTS = (BrokenPipeError, ConnectionResetError, ConnectionAbortedError)
CLIENT = (
    "<script>/* Live reload, injected by scripts/serve_site.py; not part of the site. */"
    "(function(){var es=new EventSource('" + RELOAD_PATH + "');"
    "es.addEventListener('css',function(){document.querySelectorAll('link[rel=stylesheet]').forEach(function(l){"
    "if(l.href.indexOf(location.origin)!==0)return;var u=new URL(l.href);u.searchParams.set('v',Date.now());l.href=u.href;});});"
    "es.addEventListener('reload',function(){location.reload();});})();</script>"
)


def snapshot(root: Path) -> dict[Path, float]:
    """Map every file under `root` to its modification time.

    Hidden files and folders are skipped. Files removed between listing and stat are ignored.
    """
    times: dict[Path, float] = {}
    for path in root.rglob("*"):
        if any(part.startswith(".") for part in path.relative_to(root).parts):
            continue
        try:
            if path.is_file():
                times[path] = path.stat().st_mtime
        except FileNotFoundError:
            continue
    return times


def change_kind(before: dict[Path, float], after: dict[Path, float]) -> str | None:
    """Classify the difference between two snapshots.

    Returns None when nothing changed, "css" when every changed, added, or removed file is a
    stylesheet, and "reload" otherwise.
    """
    changed = {p for p in before.keys() | after.keys() if before.get(p) != after.get(p)}
    if not changed:
        return None
    return "css" if all(p.suffix == ".css" for p in changed) else "reload"


def inject(html: bytes) -> bytes:
    """Insert the live-reload client before the last `</body>`, or append it when there is none.

    Works on bytes, so pages in any ASCII-compatible encoding pass through unchanged.
    """
    client = CLIENT.encode("utf-8")
    index = html.lower().rfind(b"</body>")
    return html + client if index < 0 else html[:index] + client + html[index:]


class Handler(http.server.SimpleHTTPRequestHandler):
    """Static file handler that disables caching, injects the reload client, and streams change events."""

    def end_headers(self) -> None:
        """Send `Cache-Control: no-store` with every response so edits always show on reload."""
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def do_GET(self) -> None:
        """Serve the event stream, an HTML page with the client injected, or a plain static file."""
        if self.path.split("?", 1)[0] == RELOAD_PATH:
            self.stream_changes()
            return
        self.serve(include_body=True)

    def do_HEAD(self) -> None:
        """Answer HEAD with the same headers GET would send, including the injected length."""
        self.serve(include_body=False)

    def html_target(self) -> Path | None:
        """The HTML file this request serves with the client injected, or None for anything else.

        A directory URL without a trailing slash returns None so the base class can redirect it.
        """
        route = self.path.split("?", 1)[0]
        target = Path(self.translate_path(self.path))
        if target.is_dir():
            if not route.endswith("/"):
                return None
            target = target / "index.html"
        return target if target.suffix == ".html" and target.is_file() else None

    def serve(self, include_body: bool) -> None:
        """Send an HTML page with the reload client injected, or defer to the static file handler."""
        target = self.html_target()
        if target is None:
            super().do_GET() if include_body else super().do_HEAD()
            return
        body = inject(target.read_bytes())
        try:
            self.send_response(200)
            self.send_header("Content-Type", "text/html")  # each page declares its own charset
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            if include_body:
                self.wfile.write(body)
        except DISCONNECTS:
            return

    def stream_changes(self) -> None:
        """Hold the connection open and send an event each time the files under the root change."""
        root = Path(self.directory)
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.end_headers()
        before = snapshot(root)
        try:
            self.wfile.write(b": connected\n\n")
            self.wfile.flush()
            last_write = time.monotonic()
            while True:
                time.sleep(POLL_SECONDS)
                after = snapshot(root)
                kind = change_kind(before, after)
                before = after
                if kind:
                    self.wfile.write(f"event: {kind}\ndata: {time.time()}\n\n".encode())
                elif time.monotonic() - last_write >= PING_SECONDS:
                    self.wfile.write(b": ping\n\n")
                else:
                    continue
                self.wfile.flush()
                last_write = time.monotonic()
        except DISCONNECTS:
            return

    def log_message(self, format: str, *args: object) -> None:
        """Log requests as usual, except the long-lived reload stream."""
        if RELOAD_PATH not in str(args[0] if args else ""):
            super().log_message(format, *args)


def main() -> None:
    """Parse arguments and serve until interrupted."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--root", type=Path, default=REPO / "site")
    args = parser.parse_args()
    root = args.root.resolve()
    handler = functools.partial(Handler, directory=str(root))
    server = http.server.ThreadingHTTPServer(("127.0.0.1", args.port), handler)
    server.daemon_threads = True
    print(f"Serving {root} at http://localhost:{args.port}/ with live reload. Ctrl+C to stop.", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
