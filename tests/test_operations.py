from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from repoframe.mode import get_mode, set_mode
from repoframe.operations import OperationManager, OperationRequestError
from repoframe.state import load_and_validate, new_state, write_state_atomic


def git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=True,
    )


def initialize_repo(repo: Path) -> None:
    git(repo, "init")
    git(repo, "config", "user.name", "RepoFrame Test")
    git(repo, "config", "user.email", "repoframe@example.test")
    (repo / "app.py").write_text("print('initial')\n", encoding="utf-8")
    git(repo, "add", "app.py")
    git(repo, "commit", "-m", "Initial commit")


def wait_for(manager: OperationManager, operation_id: str) -> dict:
    deadline = time.time() + 5
    while time.time() < deadline:
        payload = manager.get(operation_id)
        if payload["status"] not in {"queued", "running"}:
            return payload
        time.sleep(0.01)
    raise AssertionError("operation did not finish")


class FakeProvider:
    name = "codex"
    available = True

    def __init__(self) -> None:
        self.analysis_calls = 0
        self.triage_route = "direct"
        self.invalid_final = False
        self.block_commit: threading.Event | None = None
        self.release_commit: threading.Event | None = None

    def generate_commit(self, repo: Path, inspection: dict) -> dict:
        if self.block_commit and self.release_commit:
            self.block_commit.set()
            self.release_commit.wait(3)
        return {"subject": "test: generated proposal", "body": "", "summary": "All changes."}

    def _patch(self) -> dict:
        if self.invalid_final:
            return {
                "disposition": "apply",
                "summary": "Invalid.",
                "add_nodes": [],
                "update_nodes": [{"id": "implement", "set": {"depends_on": ["missing"]}}],
                "result_node_ids": ["implement"],
            }
        return {
            "disposition": "apply",
            "summary": "Inserted a review stage.",
            "add_nodes": [
                {
                    "id": "review-change",
                    "title": "Review change",
                    "status": "active",
                    "depends_on": ["inspect"],
                }
            ],
            "update_nodes": [
                {
                    "id": "implement",
                    "set": {"status": "pending", "depends_on": ["review-change"]},
                }
            ],
            "result_node_ids": ["review-change", "implement"],
        }

    def triage_intervention(self, repo: Path, state: dict, intervention: dict) -> dict:
        if self.triage_route == "parallel":
            return {
                "route": "parallel",
                "summary": "Needs two checks.",
                "analysis_requests": [
                    {"id": "one", "prompt": "Inspect one."},
                    {"id": "two", "prompt": "Inspect two."},
                ],
            }
        if self.triage_route == "needs_user":
            return {"route": "needs_user", "summary": "Choose an approach.", "analysis_requests": []}
        return {
            "route": "direct",
            "summary": "Direct.",
            "analysis_requests": [],
            "patch": self._patch(),
        }

    def analyze(self, repo: Path, request: dict[str, str]) -> dict:
        self.analysis_calls += 1
        return {"summary": request["id"], "findings": ["Safe."]}

    def finalize_intervention(
        self,
        repo: Path,
        state: dict,
        intervention: dict,
        analyses: list[dict],
        validation_issues: list[dict] | None = None,
    ) -> dict:
        return self._patch()

    def cancel(self) -> None:
        if self.release_commit:
            self.release_commit.set()


def long_run_state_v1() -> dict:
    state = new_state("Ship auth", None, [], [])
    state["schema_version"] = 1
    state.pop("interventions")
    state["nodes"] = [
        {"id": "inspect", "title": "Inspect", "status": "done", "depends_on": []},
        {
            "id": "implement",
            "title": "Implement",
            "status": "active",
            "depends_on": ["inspect"],
        },
    ]
    return state


class OperationManagerTests(unittest.TestCase):
    def test_prepare_and_commit_all_changes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo = Path(temp_dir)
            initialize_repo(repo)
            set_mode(repo, "iteration")
            (repo / "app.py").write_text("print('changed')\n", encoding="utf-8")
            (repo / "new.txt").write_text("new\n", encoding="utf-8")
            manager = OperationManager(repo, provider=FakeProvider(), recover_interrupted=False)
            started = manager.start("git.prepare_commit", {"intent": "commit"})
            prepared = wait_for(manager, started["id"])
            self.assertEqual("completed", prepared["status"])
            proposal = prepared["result"]
            confirmed = manager.start(
                "git.commit",
                {
                    "proposal_id": proposal["proposal_id"],
                    "subject": proposal["subject"],
                    "body": proposal["body"],
                },
            )
            committed = wait_for(manager, confirmed["id"])
            self.assertEqual("completed", committed["status"])
            self.assertEqual("", git(repo, "status", "--porcelain").stdout)
            self.assertEqual("test: generated proposal", git(repo, "log", "-1", "--format=%s").stdout.strip())

    def test_intervention_lazily_upgrades_v1_and_applies_patch(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo = Path(temp_dir)
            initialize_repo(repo)
            state_path = repo / ".repoframe/state.json"
            write_state_atomic(state_path, long_run_state_v1())
            set_mode(repo, "long-run")
            manager = OperationManager(repo, provider=FakeProvider(), recover_interrupted=False)
            started = manager.start(
                "intervention.create",
                {"goal_id": "ship-auth", "target_node_id": "implement", "text": "Add review."},
            )
            result = wait_for(manager, started["id"])
            self.assertEqual("completed", result["status"])
            state, _, issues = load_and_validate(state_path)
            self.assertEqual([], issues)
            self.assertEqual(2, state["schema_version"])
            self.assertEqual("incorporated", state["interventions"][0]["status"])
            self.assertEqual("active", next(node for node in state["nodes"] if node["id"] == "review-change")["status"])

    def test_parallel_route_runs_at_most_two_read_only_analyses(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo = Path(temp_dir)
            initialize_repo(repo)
            write_state_atomic(repo / ".repoframe/state.json", long_run_state_v1())
            set_mode(repo, "long-run")
            provider = FakeProvider()
            provider.triage_route = "parallel"
            manager = OperationManager(repo, provider=provider, recover_interrupted=False)
            started = manager.start(
                "intervention.create",
                {"goal_id": "ship-auth", "target_node_id": "implement", "text": "Analyze both boundaries."},
            )
            result = wait_for(manager, started["id"])
            self.assertEqual("completed", result["status"])
            self.assertEqual(2, provider.analysis_calls)

    def test_invalid_patch_twice_preserves_dag_and_marks_needs_user(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo = Path(temp_dir)
            initialize_repo(repo)
            state_path = repo / ".repoframe/state.json"
            original = long_run_state_v1()
            write_state_atomic(state_path, original)
            set_mode(repo, "long-run")
            provider = FakeProvider()
            provider.invalid_final = True
            manager = OperationManager(repo, provider=provider, recover_interrupted=False)
            started = manager.start(
                "intervention.create",
                {"goal_id": "ship-auth", "target_node_id": "implement", "text": "Invalid route."},
            )
            result = wait_for(manager, started["id"])
            self.assertEqual("failed", result["status"])
            state, _, issues = load_and_validate(state_path)
            self.assertEqual([], issues)
            self.assertEqual(original["nodes"], state["nodes"])
            self.assertEqual("needs_user", state["interventions"][0]["status"])

    def test_wrong_mode_and_archived_goal_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo = Path(temp_dir)
            initialize_repo(repo)
            write_state_atomic(repo / ".repoframe/state.json", long_run_state_v1())
            manager = OperationManager(repo, provider=FakeProvider(), recover_interrupted=False)
            set_mode(repo, "iteration")
            with self.assertRaises(OperationRequestError) as caught:
                manager.start(
                    "intervention.create",
                    {"goal_id": "ship-auth", "target_node_id": "implement", "text": "No."},
                )
            self.assertEqual("wrong_mode", caught.exception.code)
            set_mode(repo, "long-run")
            started = manager.start(
                "intervention.create",
                {"goal_id": "archived", "target_node_id": "implement", "text": "No."},
            )
            result = wait_for(manager, started["id"])
            self.assertEqual("failed", result["status"])
            self.assertEqual("goal_read_only", result["error"]["code"])

    def test_mode_switch_is_blocked_while_agent_runs(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo = Path(temp_dir)
            initialize_repo(repo)
            set_mode(repo, "iteration")
            (repo / "app.py").write_text("changed\n", encoding="utf-8")
            provider = FakeProvider()
            provider.block_commit = threading.Event()
            provider.release_commit = threading.Event()
            manager = OperationManager(repo, provider=provider, recover_interrupted=False)
            started = manager.start("git.prepare_commit", {"intent": "commit"})
            self.assertTrue(provider.block_commit.wait(2))
            with self.assertRaises(OperationRequestError) as caught:
                manager.switch_mode("long-run")
            self.assertEqual("agent_busy", caught.exception.code)
            provider.release_commit.set()
            wait_for(manager, started["id"])
            manager.switch_mode("long-run")
            self.assertEqual("long-run", get_mode(repo))

    def test_recover_interrupted_marks_needs_user(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo = Path(temp_dir)
            initialize_repo(repo)
            state = long_run_state_v1()
            state["schema_version"] = 2
            state["interventions"] = [
                {
                    "id": "intervention-stale",
                    "target_node_id": "implement",
                    "text": "Resume me.",
                    "status": "resolving",
                    "created_at": "2026-09-03T00:00:00Z",
                }
            ]
            write_state_atomic(repo / ".repoframe/state.json", state)
            OperationManager(repo, provider=FakeProvider(), recover_interrupted=True)
            payload = json.loads((repo / ".repoframe/state.json").read_text(encoding="utf-8"))
            self.assertEqual("needs_user", payload["interventions"][0]["status"])
