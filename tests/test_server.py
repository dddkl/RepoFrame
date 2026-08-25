from __future__ import annotations

import json
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from repoframe.initialize import initialize
from repoframe.server import create_server, run_viewer


class RunningServer:
    def __init__(self, repo: Path):
        self.server = create_server(repo, 0)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    def __enter__(self) -> str:
        self.thread.start()
        return f"http://127.0.0.1:{self.server.server_address[1]}"

    def __exit__(self, *args: object) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)


def fetch(url: str, *, headers: dict[str, str] | None = None, method: str = "GET"):
    return urlopen(Request(url, headers=headers or {}, method=method), timeout=2)


class ServerTests(unittest.TestCase):
    def test_serves_viewer_assets_and_security_headers(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo = Path(temp_dir)
            initialize(repo, "Ship auth", None, [], [], "none")
            with RunningServer(repo) as base:
                with fetch(base + "/") as response:
                    html = response.read().decode("utf-8")
                    self.assertEqual("text/html; charset=utf-8", response.headers["Content-Type"])
                    self.assertIn("default-src 'self'", response.headers["Content-Security-Policy"])
                    self.assertIn("RepoFrame", html)
                with fetch(base + "/assets/app.css") as response:
                    self.assertEqual("text/css; charset=utf-8", response.headers["Content-Type"])
                    self.assertIn(b"prefers-reduced-motion", response.read())
                with fetch(base + "/assets/app.js") as response:
                    self.assertIn("javascript", response.headers["Content-Type"])
                    script = response.read()
                    self.assertIn(b"/api/v1/state", script)
                    self.assertIn(b"last valid snapshot", script)
                with fetch(base + "/favicon.ico") as response:
                    self.assertEqual(204, response.status)

    def test_state_endpoint_uses_etag_and_304(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo = Path(temp_dir)
            initialize(repo, "Ship auth", None, [], [], "none")
            with RunningServer(repo) as base:
                with fetch(base + "/api/v1/state") as response:
                    payload = json.loads(response.read())
                    etag = response.headers["ETag"]
                self.assertEqual("Ship auth", payload["goal"]["title"])
                with self.assertRaises(HTTPError) as caught:
                    fetch(base + "/api/v1/state", headers={"If-None-Match": etag})
                self.assertEqual(304, caught.exception.code)

    def test_state_etag_changes_with_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo = Path(temp_dir)
            initialize(repo, "Ship auth", None, [], [], "none")
            state_path = repo / ".repoframe/state.json"
            with RunningServer(repo) as base:
                with fetch(base + "/api/v1/state") as response:
                    first = response.headers["ETag"]
                payload = json.loads(state_path.read_text(encoding="utf-8"))
                payload["goal"]["outcome"] = "A changed outcome"
                state_path.write_text(json.dumps(payload), encoding="utf-8")
                with fetch(base + "/api/v1/state") as response:
                    second = response.headers["ETag"]
            self.assertNotEqual(first, second)

    def test_invalid_state_returns_422_diagnostics(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo = Path(temp_dir)
            state_dir = repo / ".repoframe"
            state_dir.mkdir()
            (state_dir / "state.json").write_text("{", encoding="utf-8")
            with RunningServer(repo) as base:
                with self.assertRaises(HTTPError) as caught:
                    fetch(base + "/api/v1/state")
                payload = json.loads(caught.exception.read())
            self.assertEqual(422, caught.exception.code)
            self.assertEqual("invalid_state", payload["error"])
            self.assertEqual("json.invalid", payload["issues"][0]["code"])

    def test_malformed_status_type_returns_422_instead_of_dropping_connection(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo = Path(temp_dir)
            initialize(repo, "Ship auth", None, [], [], "none")
            state_path = repo / ".repoframe/state.json"
            payload = json.loads(state_path.read_text(encoding="utf-8"))
            payload["goal"]["status"] = []
            state_path.write_text(json.dumps(payload), encoding="utf-8")
            with RunningServer(repo) as base:
                with self.assertRaises(HTTPError) as caught:
                    fetch(base + "/api/v1/state")
                response = json.loads(caught.exception.read())
            self.assertEqual(422, caught.exception.code)
            self.assertEqual("schema.enum", response["issues"][0]["code"])

    def test_missing_state_returns_404(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            with RunningServer(Path(temp_dir)) as base:
                with self.assertRaises(HTTPError) as caught:
                    fetch(base + "/api/v1/state")
                payload = json.loads(caught.exception.read())
            self.assertEqual(404, caught.exception.code)
            self.assertEqual("state_not_found", payload["error"])

    def test_health_unknown_routes_write_methods_and_traversal(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo = Path(temp_dir)
            initialize(repo, "Ship auth", None, [], [], "none")
            (repo / "secret.txt").write_text("secret", encoding="utf-8")
            with RunningServer(repo) as base:
                with fetch(base + "/healthz") as response:
                    self.assertEqual({"status": "ok"}, json.loads(response.read()))
                for path in ("/unknown", "/assets/../secret.txt", "/secret.txt"):
                    with self.assertRaises(HTTPError) as caught:
                        fetch(base + path)
                    self.assertEqual(404, caught.exception.code)
                with self.assertRaises(HTTPError) as caught:
                    fetch(base + "/api/v1/state", method="POST")
                self.assertEqual(405, caught.exception.code)


class ViewerRunnerTests(unittest.TestCase):
    def test_rejects_port_outside_user_range(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            self.assertEqual(2, run_viewer(Path(temp_dir), 0, open_browser=False))

    def test_reports_occupied_port(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir, patch(
            "repoframe.server.create_server", side_effect=OSError("address in use")
        ):
            self.assertEqual(1, run_viewer(Path(temp_dir), 7331, open_browser=False))

    def test_opens_browser_once_and_closes_server(self) -> None:
        fake_server = Mock()
        with tempfile.TemporaryDirectory() as temp_dir, patch(
            "repoframe.server.create_server", return_value=fake_server
        ), patch("repoframe.server.webbrowser.open") as browser_open:
            self.assertEqual(0, run_viewer(Path(temp_dir), 7331, open_browser=True))
        browser_open.assert_called_once_with("http://127.0.0.1:7331/")
        fake_server.serve_forever.assert_called_once_with()
        fake_server.server_close.assert_called_once_with()

    def test_no_open_skips_browser(self) -> None:
        fake_server = Mock()
        with tempfile.TemporaryDirectory() as temp_dir, patch(
            "repoframe.server.create_server", return_value=fake_server
        ), patch("repoframe.server.webbrowser.open") as browser_open:
            self.assertEqual(0, run_viewer(Path(temp_dir), 7331, open_browser=False))
        browser_open.assert_not_called()


if __name__ == "__main__":
    unittest.main()
