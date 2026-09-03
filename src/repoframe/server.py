"""Loopback-only RepoFrame viewer and typed interactive intent service."""

from __future__ import annotations

import hashlib
import json
import secrets
import sys
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib import resources
from pathlib import Path
from typing import Any
from urllib.parse import unquote

from .git_inspect import GitInspectionError, inspect_repository
from .operations import OperationManager, OperationRequestError
from .state import IDENTIFIER, load_and_validate


SECURITY_HEADERS = {
    "Content-Security-Policy": (
        "default-src 'self'; connect-src 'self'; img-src 'self'; script-src 'self'; "
        "style-src 'self'; base-uri 'none'; frame-ancestors 'none'; form-action 'none'"
    ),
    "Referrer-Policy": "no-referrer",
    "X-Content-Type-Options": "nosniff",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
    "Cache-Control": "no-store",
}
ASSETS = {
    "/assets/app.css": ("app.css", "text/css; charset=utf-8"),
    "/assets/app.js": ("app.js", "text/javascript; charset=utf-8"),
}
VIEW_ROUTES = {"/", "/long-run"}
MAX_JSON_BODY = 16 * 1024
TOKEN_PLACEHOLDER = "__REPOFRAME_TOKEN__"


class RepoFrameHTTPServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(
        self,
        address: tuple[str, int],
        handler: type[BaseHTTPRequestHandler],
        *,
        repo: Path,
        interactive: bool,
        manager: OperationManager,
    ) -> None:
        self.repo = repo
        self.interactive = interactive
        self.session_token = secrets.token_urlsafe(32) if interactive else ""
        self.manager = manager
        super().__init__(address, handler)


def _json_bytes(payload: Any) -> bytes:
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def _handler_for(repo: Path) -> type[BaseHTTPRequestHandler]:
    state_path = repo / ".repoframe/state.json"

    def goal_states() -> tuple[list[dict[str, Any]], dict[str, tuple[dict[str, Any], bytes]], list[dict[str, str]]]:
        candidates: list[tuple[Path, str, bool]] = [(state_path, "state.json", True)]
        goals_dir = repo / ".repoframe/goals"
        if goals_dir.exists() and goals_dir.is_dir() and goals_dir.resolve().is_relative_to(repo):
            candidates.extend((path, f"goals/{path.name}", False) for path in sorted(goals_dir.glob("*.json")))

        goals: list[dict[str, Any]] = []
        states: dict[str, tuple[dict[str, Any], bytes]] = {}
        problems: list[dict[str, str]] = []
        for path, source, current in candidates:
            if not path.exists():
                continue
            if not path.resolve().is_relative_to(repo):
                problems.append(
                    {"code": "goal.unsafe_path", "path": source, "message": "Goal snapshot resolves outside the repository."}
                )
                continue
            payload, raw, issues = load_and_validate(path)
            if issues or payload is None or raw is None:
                problems.extend(
                    {"code": issue.code, "path": f"{source}:{issue.path}", "message": issue.message}
                    for issue in issues
                )
                continue
            goal = payload["goal"]
            goal_id = goal["id"]
            if goal_id in states:
                problems.append(
                    {
                        "code": "goal.duplicate_id",
                        "path": source,
                        "message": f"Goal id '{goal_id}' is already provided by another snapshot.",
                    }
                )
                continue
            states[goal_id] = (payload, raw)
            goals.append(
                {
                    "id": goal_id,
                    "title": goal["title"],
                    "status": goal["status"],
                    "updated_at": payload["updated_at"],
                    "source": source,
                    "current": current,
                }
            )
        goals.sort(key=lambda item: (not item["current"], item["status"] == "done", item["title"].lower()))
        return goals, states, problems

    class Handler(BaseHTTPRequestHandler):
        server_version = "RepoFrame/0.3"

        @property
        def app_server(self) -> RepoFrameHTTPServer:
            return self.server  # type: ignore[return-value]

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
            try:
                self.wfile.write(body)
            except (BrokenPipeError, ConnectionResetError):
                return

        def _send_json(self, status: int, payload: Any) -> None:
            self._send(status, _json_bytes(payload), "application/json; charset=utf-8")

        def _send_etag_json(self, payload: Any, raw: bytes | None = None) -> None:
            body = _json_bytes(payload)
            etag = f'"{hashlib.sha256(raw if raw is not None else body).hexdigest()}"'
            if self.headers.get("If-None-Match") == etag:
                self._headers(304, "application/json; charset=utf-8")
                self.send_header("ETag", etag)
                self.end_headers()
                return
            self._headers(200, "application/json; charset=utf-8", len(body))
            self.send_header("ETag", etag)
            self.end_headers()
            self.wfile.write(body)

        def _redirect(self, location: str) -> None:
            self.send_response(308)
            self.send_header("Location", location)
            for name, value in SECURITY_HEADERS.items():
                self.send_header(name, value)
            self.send_header("Content-Length", "0")
            self.end_headers()

        def do_GET(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
            path = self.path.split("?", 1)[0]
            if path == "/iteration":
                self._redirect("/")
                return
            if path in VIEW_ROUTES or (path.startswith("/long-run/") and IDENTIFIER.fullmatch(unquote(path[10:]))):
                text = resources.files("repoframe.web").joinpath("index.html").read_text(encoding="utf-8")
                text = text.replace(TOKEN_PLACEHOLDER, self.app_server.session_token)
                self._send(200, text.encode("utf-8"), "text/html; charset=utf-8")
                return
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
            if path == "/api/v1/iteration":
                self._iteration_response()
                return
            if path == "/api/v1/goals":
                goals, _, issues = goal_states()
                self._send_etag_json({"goals": goals, "issues": issues})
                return
            if path.startswith("/api/v1/goals/"):
                self._goal_response(unquote(path[len("/api/v1/goals/") :]))
                return
            if path == "/api/v1/runtime":
                self._send_json(
                    200,
                    self.app_server.manager.runtime(interactive=self.app_server.interactive),
                )
                return
            if path.startswith("/api/v1/operations/"):
                operation_id = unquote(path[len("/api/v1/operations/") :])
                if "/" not in operation_id:
                    try:
                        self._send_json(200, self.app_server.manager.get(operation_id))
                    except OperationRequestError as exc:
                        self._send_json(exc.status, {"error": exc.code, "message": str(exc)})
                    return
            self._send_json(404, {"error": "not_found"})

        def _iteration_response(self) -> None:
            try:
                payload = inspect_repository(repo)
            except GitInspectionError as exc:
                self._send_json(409, {"error": "git_unavailable", "message": str(exc)})
                return
            self._send_etag_json(payload)

        def _goal_response(self, goal_id: str) -> None:
            if not IDENTIFIER.fullmatch(goal_id):
                self._send_json(404, {"error": "goal_not_found"})
                return
            _, states, _ = goal_states()
            state = states.get(goal_id)
            if state is None:
                self._send_json(404, {"error": "goal_not_found"})
                return
            payload, raw = state
            self._send_etag_json(payload, raw)

        def _state_response(self) -> None:
            payload, raw, issues = load_and_validate(state_path)
            if raw is None and issues and issues[0].code == "file.not_found":
                self._send_json(404, {"error": "state_not_found"})
                return
            if issues:
                self._send_json(422, {"error": "invalid_state", "issues": [issue.to_dict() for issue in issues]})
                return
            assert payload is not None and raw is not None
            self._send_etag_json(payload, raw)

        def _authorized(self) -> bool:
            if not self.app_server.interactive:
                self._method_not_allowed()
                return False
            host, port = self.app_server.server_address
            expected_origin = f"http://{host}:{port}"
            expected_host = f"{host}:{port}"
            origin = self.headers.get("Origin", "")
            request_host = self.headers.get("Host", "")
            token = self.headers.get("X-RepoFrame-Token", "")
            if (
                origin != expected_origin
                or request_host != expected_host
                or not secrets.compare_digest(token, self.app_server.session_token)
            ):
                self._send_json(403, {"error": "forbidden", "message": "Interactive request was not authorized."})
                return False
            return True

        def _read_json(self) -> object | None:
            raw_length = self.headers.get("Content-Length")
            try:
                length = int(raw_length or "0")
            except ValueError:
                self._send_json(400, {"error": "invalid_request", "message": "Invalid Content-Length."})
                return None
            if length <= 0:
                self._send_json(400, {"error": "invalid_request", "message": "JSON body size is invalid."})
                return None
            if length > MAX_JSON_BODY:
                # Consume the authenticated loopback request in bounded chunks before
                # responding. On Windows, closing with unread request bytes can reset
                # the connection before the client receives the intended 413.
                remaining = length
                while remaining:
                    chunk = self.rfile.read(min(remaining, 64 * 1024))
                    if not chunk:
                        break
                    remaining -= len(chunk)
                self._send_json(413, {"error": "invalid_request", "message": "JSON body size is invalid."})
                return None
            if self.headers.get_content_type() != "application/json":
                self._send_json(415, {"error": "unsupported_media_type"})
                return None
            try:
                return json.loads(self.rfile.read(length).decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                self._send_json(400, {"error": "invalid_json"})
                return None

        def do_POST(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
            if not self._authorized():
                return
            path = self.path.split("?", 1)[0]
            body = self._read_json()
            if body is None:
                return
            try:
                if path == "/api/v1/mode":
                    if not isinstance(body, dict) or set(body) != {"mode"} or not isinstance(body["mode"], str):
                        raise OperationRequestError("Mode request must contain one string field named 'mode'.")
                    self._send_json(200, self.app_server.manager.switch_mode(body["mode"]))
                    return
                if path == "/api/v1/operations":
                    if not isinstance(body, dict) or set(body) != {"type", "payload"}:
                        raise OperationRequestError("Operation request must contain type and payload.")
                    if not isinstance(body["type"], str):
                        raise OperationRequestError("Operation type must be a string.")
                    self._send_json(202, self.app_server.manager.start(body["type"], body["payload"]))
                    return
                prefix = "/api/v1/operations/"
                suffix = "/cancel"
                if path.startswith(prefix) and path.endswith(suffix):
                    operation_id = unquote(path[len(prefix) : -len(suffix)])
                    if not operation_id or "/" in operation_id:
                        raise OperationRequestError("Operation was not found.", code="operation_not_found", status=404)
                    if body != {}:
                        raise OperationRequestError("Cancel request body must be an empty object.")
                    self._send_json(200, self.app_server.manager.cancel(operation_id))
                    return
                self._send_json(404, {"error": "not_found"})
            except OperationRequestError as exc:
                self._send_json(exc.status, {"error": exc.code, "message": str(exc)})

        def _method_not_allowed(self) -> None:
            body = _json_bytes({"error": "method_not_allowed"})
            self._headers(405, "application/json; charset=utf-8", len(body))
            self.send_header("Allow", "GET")
            self.end_headers()
            self.wfile.write(body)

        do_PUT = _method_not_allowed
        do_PATCH = _method_not_allowed
        do_DELETE = _method_not_allowed

    return Handler


def create_server(
    repo: Path,
    port: int,
    *,
    interactive: bool = False,
    manager: OperationManager | None = None,
) -> RepoFrameHTTPServer:
    """Create a loopback-only server. Port 0 is supported for tests."""
    if port < 0 or port > 65535:
        raise ValueError("Port must be between 0 and 65535.")
    resolved = repo.resolve()
    runtime = manager or OperationManager(resolved, recover_interrupted=interactive)
    return RepoFrameHTTPServer(
        ("127.0.0.1", port),
        _handler_for(resolved),
        repo=resolved,
        interactive=interactive,
        manager=runtime,
    )


def _run_server(repo: Path, port: int, *, open_browser: bool, interactive: bool) -> int:
    command = "interact" if interactive else "view"
    if port < 1 or port > 65535:
        print(f"repoframe {command}: --port must be between 1 and 65535.", file=sys.stderr)
        return 2
    try:
        server = create_server(repo, port, interactive=interactive)
    except OSError as exc:
        print(f"repoframe {command}: unable to bind 127.0.0.1:{port}: {exc}", file=sys.stderr)
        return 1
    url = f"http://127.0.0.1:{port}/"
    label = "interactive workbench" if interactive else "viewer"
    print(f"RepoFrame {label}: {url}")
    print("Press Ctrl+C to stop.")
    if open_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print(f"\nRepoFrame {label} stopped.")
    finally:
        server.manager.close()
        server.server_close()
    return 0


def run_viewer(repo: Path, port: int, *, open_browser: bool = True) -> int:
    """Run the read-only viewer until interrupted."""
    return _run_server(repo, port, open_browser=open_browser, interactive=False)


def run_interactive(repo: Path, port: int, *, open_browser: bool = True) -> int:
    """Run the typed local intent service until interrupted."""
    return _run_server(repo, port, open_browser=open_browser, interactive=True)
