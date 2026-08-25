"""Local, read-only HTTP server for the RepoFrame DAG viewer."""

from __future__ import annotations

import hashlib
import json
import sys
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib import resources
from pathlib import Path
from typing import Any

from .state import load_and_validate


SECURITY_HEADERS = {
    "Content-Security-Policy": "default-src 'self'; connect-src 'self'; img-src 'self'; script-src 'self'; style-src 'self'; base-uri 'none'; frame-ancestors 'none'",
    "Referrer-Policy": "no-referrer",
    "X-Content-Type-Options": "nosniff",
    "Cache-Control": "no-store",
}
ASSETS = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/assets/app.css": ("app.css", "text/css; charset=utf-8"),
    "/assets/app.js": ("app.js", "text/javascript; charset=utf-8"),
}


class RepoFrameHTTPServer(ThreadingHTTPServer):
    daemon_threads = True


def _json_bytes(payload: Any) -> bytes:
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def _handler_for(repo: Path) -> type[BaseHTTPRequestHandler]:
    state_path = repo / ".repoframe/state.json"

    class Handler(BaseHTTPRequestHandler):
        server_version = "RepoFrame/0.1"

        def log_message(self, format: str, *args: object) -> None:
            return

        def _headers(self, status: int, content_type: str, length: int | None = None) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            if length is not None:
                self.send_header("Content-Length", str(length))
            for name, value in SECURITY_HEADERS.items():
                self.send_header(name, value)

        def _send(self, status: int, body: bytes, content_type: str) -> None:
            self._headers(status, content_type, len(body))
            self.end_headers()
            self.wfile.write(body)

        def _send_json(self, status: int, payload: Any) -> None:
            self._send(status, _json_bytes(payload), "application/json; charset=utf-8")

        def do_GET(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
            path = self.path.split("?", 1)[0]
            if path in ASSETS:
                filename, content_type = ASSETS[path]
                body = resources.files("repoframe.web").joinpath(filename).read_bytes()
                self._send(200, body, content_type)
                return
            if path == "/favicon.ico":
                self._headers(204, "image/x-icon", 0)
                self.end_headers()
                return
            if path == "/healthz":
                self._send_json(200, {"status": "ok"})
                return
            if path == "/api/v1/state":
                self._state_response()
                return
            self._send_json(404, {"error": "not_found"})

        def _state_response(self) -> None:
            payload, raw, issues = load_and_validate(state_path)
            if raw is None and issues and issues[0].code == "file.not_found":
                self._send_json(404, {"error": "state_not_found"})
                return
            if issues:
                self._send_json(422, {"error": "invalid_state", "issues": [issue.to_dict() for issue in issues]})
                return
            assert payload is not None and raw is not None
            etag = f'"{hashlib.sha256(raw).hexdigest()}"'
            if self.headers.get("If-None-Match") == etag:
                self._headers(304, "application/json; charset=utf-8")
                self.send_header("ETag", etag)
                self.end_headers()
                return
            body = _json_bytes(payload)
            self._headers(200, "application/json; charset=utf-8", len(body))
            self.send_header("ETag", etag)
            self.end_headers()
            self.wfile.write(body)

        def _method_not_allowed(self) -> None:
            body = _json_bytes({"error": "method_not_allowed"})
            self._headers(405, "application/json; charset=utf-8", len(body))
            self.send_header("Allow", "GET")
            self.end_headers()
            self.wfile.write(body)

        do_POST = _method_not_allowed
        do_PUT = _method_not_allowed
        do_PATCH = _method_not_allowed
        do_DELETE = _method_not_allowed

    return Handler


def create_server(repo: Path, port: int) -> RepoFrameHTTPServer:
    """Create a loopback-only RepoFrame server. Port 0 is supported for tests."""
    if port < 0 or port > 65535:
        raise ValueError("Port must be between 0 and 65535.")
    return RepoFrameHTTPServer(("127.0.0.1", port), _handler_for(repo.resolve()))


def run_viewer(repo: Path, port: int, *, open_browser: bool = True) -> int:
    """Run the viewer until interrupted."""
    if port < 1 or port > 65535:
        print("repoframe view: --port must be between 1 and 65535.", file=sys.stderr)
        return 2
    try:
        server = create_server(repo, port)
    except OSError as exc:
        print(f"repoframe view: unable to bind 127.0.0.1:{port}: {exc}", file=sys.stderr)
        return 1
    url = f"http://127.0.0.1:{port}/"
    print(f"RepoFrame viewer: {url}")
    print("Press Ctrl+C to stop.")
    if open_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nRepoFrame viewer stopped.")
    finally:
        server.server_close()
    return 0
