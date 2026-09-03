from __future__ import annotations

import json
import re
import subprocess
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
from repoframe.operations import OperationManager
from repoframe.server import create_server, run_viewer
from repoframe.state import new_state


class RunningServer:
    def __init__(self, repo: Path, *, interactive: bool = False, manager: OperationManager | None = None):
        self.server = create_server(repo, 0, interactive=interactive, manager=manager)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    def __enter__(self) -> str:
        self.thread.start()
        return f"http://127.0.0.1:{self.server.server_address[1]}"

    def __exit__(self, *args: object) -> None:
        self.server.shutdown()
        self.server.manager.close()
        self.server.server_close()
        self.thread.join(timeout=2)


def fetch(
    url: str,
    *,
    headers: dict[str, str] | None = None,
    method: str = "GET",
    body: object | None = None,
):
    data = json.dumps(body).encode("utf-8") if body is not None else None
    request_headers = dict(headers or {})
    if body is not None:
        request_headers["Content-Type"] = "application/json"
    return urlopen(Request(url, headers=request_headers, data=data, method=method), timeout=2)


def interactive_headers(base: str) -> dict[str, str]:
    with fetch(base + "/") as response:
        html = response.read().decode("utf-8")
    match = re.search(r'<meta name="repoframe-token" content="([^"]+)">', html)
    if not match:
        raise AssertionError("interactive session token not found")
    return {"Origin": base, "X-RepoFrame-Token": match.group(1)}


class ServerFakeProvider:
    name = "codex"
    available = True

    def generate_commit(self, repo: Path, inspection: dict) -> dict:
        return {"subject": "test: server proposal", "body": "", "summary": "Prepared."}

    def triage_intervention(self, repo: Path, state: dict, intervention: dict) -> dict:
        return {
            "route": "needs_user",
            "summary": "More input.",
            "analysis_requests": [],
        }

    def analyze(self, repo: Path, request: dict) -> dict:
        return {"summary": "Done.", "findings": []}

    def finalize_intervention(self, repo: Path, state: dict, intervention: dict, analyses: list, validation_issues=None):
        raise AssertionError("not expected")

    def cancel(self) -> None:
        return


def initialize_git(repo: Path) -> None:
    subprocess.run(["git", "-C", str(repo), "init"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.name", "RepoFrame Test"], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.email", "repoframe@example.test"], check=True)
    (repo / "README.md").write_text("# Test\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "add", "README.md"], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-m", "Initial commit"], check=True, capture_output=True)


class ServerTests(unittest.TestCase):
    def test_serves_viewer_assets_and_security_headers(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo = Path(temp_dir)
            initialize(repo, "Ship auth", None, [], [], "none")
            with RunningServer(repo) as base:
                with fetch(base + "/") as response:
                    html = response.read().decode("utf-8")
                    self.assertEqual("text/html; charset=utf-8", response.headers["Content-Type"])
                    self.assertTrue(response.headers["Server"].startswith("RepoFrame/0.3"))
                    self.assertIn("default-src 'self'", response.headers["Content-Security-Policy"])
                    self.assertIn("RepoFrame", html)
                    self.assertIn("iteration-card", html)
                with fetch(base + "/iteration") as response:
                    self.assertEqual(base + "/", response.url)
                    self.assertIn(b"Iteration", response.read())
                with fetch(base + "/long-run/ship-auth") as response:
                    self.assertIn(b"Execution path", response.read())
                with fetch(base + "/assets/app.css") as response:
                    self.assertEqual("text/css; charset=utf-8", response.headers["Content-Type"])
                    stylesheet = response.read()
                    self.assertIn(b"prefers-reduced-motion", stylesheet)
                    self.assertIn(b"top: calc(50% + var(--bar-height) / 2)", stylesheet)
                    self.assertIn(b".goal-menu", stylesheet)
                    self.assertNotIn(b".iteration-card.is-minimized", stylesheet)
                with fetch(base + "/assets/app.js") as response:
                    self.assertIn("javascript", response.headers["Content-Type"])
                    script = response.read()
                    self.assertIn(b"/api/v1/iteration", script)
                    self.assertIn(b"/api/v1/goals", script)
                    self.assertIn(b"/api/v1/operations", script)
                    self.assertIn(b"setGoalMenuOpen", script)
                    self.assertIn(b'addEventListener("wheel"', script)
                    self.assertNotIn(b"setIterationMinimized", script)
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

    def test_iteration_endpoint_works_without_repoframe_state(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo = Path(temp_dir)
            initialize_git(repo)
            initialize(repo, None, None, [], [], "none")
            self.assertFalse((repo / ".repoframe/state.json").exists())
            (repo / "README.md").write_text("# Changed\n", encoding="utf-8")
            with RunningServer(repo) as base:
                with fetch(base + "/api/v1/iteration") as response:
                    payload = json.loads(response.read())
                    etag = response.headers["ETag"]
                with self.assertRaises(HTTPError) as caught:
                    fetch(base + "/api/v1/iteration", headers={"If-None-Match": etag})
            self.assertEqual(304, caught.exception.code)
            self.assertEqual(3, payload["working_changes"]["changed_files"])
            paths = {item["path"] for item in payload["working_changes"]["files"]}
            self.assertEqual(
                {"README.md", ".repoframe/instructions.md", ".repoframe/state.schema.json"},
                paths,
            )
            self.assertEqual("Initial commit", payload["latest_commit"]["subject"])

    def test_iteration_endpoint_rejects_non_git_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            with RunningServer(Path(temp_dir)) as base:
                with self.assertRaises(HTTPError) as caught:
                    fetch(base + "/api/v1/iteration")
                payload = json.loads(caught.exception.read())
            self.assertEqual(409, caught.exception.code)
            self.assertEqual("git_unavailable", payload["error"])

    def test_goal_list_is_empty_when_iteration_has_no_state(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo = Path(temp_dir)
            initialize(repo, None, None, [], [], "none")
            with RunningServer(repo) as base:
                with fetch(base + "/api/v1/goals") as response:
                    payload = json.loads(response.read())
            self.assertEqual([], payload["goals"])
            self.assertEqual([], payload["issues"])

    def test_goal_list_and_independent_goal_endpoint(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo = Path(temp_dir)
            initialize(repo, "Ship auth", None, [], [], "none")
            archive = new_state("Retire password login", None, [], [])
            archive["goal"]["status"] = "done"
            goals_dir = repo / ".repoframe/goals"
            goals_dir.mkdir()
            (goals_dir / "retired.json").write_text(json.dumps(archive), encoding="utf-8")
            with RunningServer(repo) as base:
                with fetch(base + "/api/v1/goals") as response:
                    listing = json.loads(response.read())
                with fetch(base + "/api/v1/goals/retire-password-login") as response:
                    archived = json.loads(response.read())
            self.assertEqual(["ship-auth", "retire-password-login"], [goal["id"] for goal in listing["goals"]])
            self.assertTrue(listing["goals"][0]["current"])
            self.assertEqual("Retire password login", archived["goal"]["title"])

    def test_invalid_goal_snapshot_is_reported_without_breaking_valid_goals(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo = Path(temp_dir)
            initialize(repo, "Ship auth", None, [], [], "none")
            goals_dir = repo / ".repoframe/goals"
            goals_dir.mkdir()
            (goals_dir / "broken.json").write_text("{", encoding="utf-8")
            with RunningServer(repo) as base:
                with fetch(base + "/api/v1/goals") as response:
                    listing = json.loads(response.read())
            self.assertEqual(["ship-auth"], [goal["id"] for goal in listing["goals"]])
            self.assertEqual("json.invalid", listing["issues"][0]["code"])

    def test_health_unknown_routes_write_methods_and_traversal(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo = Path(temp_dir)
            initialize(repo, "Ship auth", None, [], [], "none")
            (repo / "secret.txt").write_text("secret", encoding="utf-8")
            with RunningServer(repo) as base:
                with fetch(base + "/healthz") as response:
                    self.assertEqual({"status": "ok"}, json.loads(response.read()))
                for path in ("/unknown", "/assets/../secret.txt", "/secret.txt", "/api/v1/goals/INVALID"):
                    with self.assertRaises(HTTPError) as caught:
                        fetch(base + path)
                    self.assertEqual(404, caught.exception.code)
                with self.assertRaises(HTTPError) as caught:
                    fetch(base + "/api/v1/state", method="POST")
                self.assertEqual(405, caught.exception.code)

    def test_runtime_is_read_only_in_view_mode(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo = Path(temp_dir)
            initialize_git(repo)
            initialize(repo, None, None, [], [], "none")
            with RunningServer(repo) as base:
                with fetch(base + "/api/v1/runtime") as response:
                    runtime = json.loads(response.read())
                self.assertFalse(runtime["interactive"])
                self.assertEqual("iteration", runtime["mode"])
                self.assertFalse(runtime["capabilities"]["commit"])
                with self.assertRaises(HTTPError) as caught:
                    fetch(base + "/api/v1/mode", method="POST", body={"mode": "long-run"})
                self.assertEqual(405, caught.exception.code)

    def test_interactive_api_requires_origin_host_and_token(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo = Path(temp_dir)
            initialize_git(repo)
            initialize(repo, None, None, [], [], "none")
            manager = OperationManager(repo, provider=ServerFakeProvider(), recover_interrupted=False)
            with RunningServer(repo, interactive=True, manager=manager) as base:
                with self.assertRaises(HTTPError) as caught:
                    fetch(base + "/api/v1/mode", method="POST", body={"mode": "long-run"})
                self.assertEqual(403, caught.exception.code)
                headers = interactive_headers(base)
                with fetch(
                    base + "/api/v1/mode",
                    headers=headers,
                    method="POST",
                    body={"mode": "long-run"},
                ) as response:
                    self.assertEqual({"mode": "long-run"}, json.loads(response.read()))
                with fetch(base + "/api/v1/runtime") as response:
                    self.assertEqual("long-run", json.loads(response.read())["mode"])

    def test_interactive_api_rejects_bad_token_and_oversized_body(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo = Path(temp_dir)
            initialize_git(repo)
            initialize(repo, None, None, [], [], "none")
            manager = OperationManager(repo, provider=ServerFakeProvider(), recover_interrupted=False)
            with RunningServer(repo, interactive=True, manager=manager) as base:
                headers = interactive_headers(base)
                bad_headers = {**headers, "X-RepoFrame-Token": "not-the-session-token"}
                with self.assertRaises(HTTPError) as caught:
                    fetch(
                        base + "/api/v1/mode",
                        headers=bad_headers,
                        method="POST",
                        body={"mode": "long-run"},
                    )
                self.assertEqual(403, caught.exception.code)

                with self.assertRaises(HTTPError) as caught:
                    fetch(
                        base + "/api/v1/operations",
                        headers=headers,
                        method="POST",
                        body={"type": "git.prepare_commit", "payload": {"intent": "x" * 17_000}},
                    )
                self.assertEqual(413, caught.exception.code)

                with self.assertRaises(HTTPError) as caught:
                    fetch(base + "/api/v1/not-a-route", headers=headers, method="POST", body={})
                self.assertEqual(404, caught.exception.code)

    def test_interactive_operation_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo = Path(temp_dir)
            initialize_git(repo)
            initialize(repo, None, None, [], [], "none")
            (repo / "README.md").write_text("# Changed\n", encoding="utf-8")
            manager = OperationManager(repo, provider=ServerFakeProvider(), recover_interrupted=False)
            with RunningServer(repo, interactive=True, manager=manager) as base:
                headers = interactive_headers(base)
                with fetch(
                    base + "/api/v1/operations",
                    headers=headers,
                    method="POST",
                    body={"type": "git.prepare_commit", "payload": {"intent": "commit"}},
                ) as response:
                    started = json.loads(response.read())
                    self.assertEqual(202, response.status)
                for _ in range(100):
                    with fetch(base + f"/api/v1/operations/{started['id']}") as response:
                        operation = json.loads(response.read())
                    if operation["status"] not in {"queued", "running"}:
                        break
                    threading.Event().wait(0.01)
                self.assertEqual("completed", operation["status"])
                self.assertEqual("test: server proposal", operation["result"]["subject"])


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
