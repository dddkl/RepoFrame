from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from repoframe.git_ops import GitOperationError, commit_all, push_current, working_tree_snapshot


def run(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=True,
    )


def initialize(repo: Path) -> None:
    run(repo, "init")
    run(repo, "config", "user.name", "RepoFrame Test")
    run(repo, "config", "user.email", "repoframe@example.test")
    (repo / "tracked.txt").write_text("initial\n", encoding="utf-8")
    run(repo, "add", "tracked.txt")
    run(repo, "commit", "-m", "Initial commit")


class GitOperationTests(unittest.TestCase):
    def test_commit_all_includes_tracked_and_untracked_changes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo = Path(temp_dir)
            initialize(repo)
            (repo / "tracked.txt").write_text("changed\n", encoding="utf-8")
            (repo / "new.txt").write_text("new\n", encoding="utf-8")
            snapshot = working_tree_snapshot(repo)
            self.assertEqual(2, snapshot["inspection"]["working_changes"]["changed_files"])
            result = commit_all(repo, snapshot["fingerprint"], "test: commit all", "Body")
            self.assertTrue(result["hash"])
            self.assertEqual("test: commit all", run(repo, "log", "-1", "--format=%s").stdout.strip())
            self.assertEqual("", run(repo, "status", "--porcelain").stdout)
            self.assertEqual("new\n", (repo / "new.txt").read_text(encoding="utf-8"))

    def test_rejects_stale_proposal_without_staging(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo = Path(temp_dir)
            initialize(repo)
            (repo / "tracked.txt").write_text("first\n", encoding="utf-8")
            snapshot = working_tree_snapshot(repo)
            (repo / "tracked.txt").write_text("second\n", encoding="utf-8")
            with self.assertRaises(GitOperationError) as caught:
                commit_all(repo, snapshot["fingerprint"], "test: stale")
            self.assertEqual("proposal_stale", caught.exception.code)
            self.assertEqual("", run(repo, "diff", "--cached", "--name-only").stdout)

    def test_rejects_empty_and_invalid_commit_message(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo = Path(temp_dir)
            initialize(repo)
            clean = working_tree_snapshot(repo)
            with self.assertRaises(GitOperationError) as caught:
                commit_all(repo, clean["fingerprint"], "test: no changes")
            self.assertEqual("no_changes", caught.exception.code)
            (repo / "tracked.txt").write_text("changed\n", encoding="utf-8")
            changed = working_tree_snapshot(repo)
            with self.assertRaises(GitOperationError) as caught:
                commit_all(repo, changed["fingerprint"], "bad\nsubject")
            self.assertEqual("invalid_message", caught.exception.code)

    def test_push_current_uses_existing_upstream(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            repo = root / "repo"
            remote = root / "remote.git"
            repo.mkdir()
            subprocess.run(["git", "init", "--bare", str(remote)], check=True, capture_output=True)
            initialize(repo)
            run(repo, "branch", "-M", "main")
            run(repo, "remote", "add", "origin", str(remote))
            run(repo, "push", "-u", "origin", "main")
            (repo / "tracked.txt").write_text("pushed\n", encoding="utf-8")
            snapshot = working_tree_snapshot(repo)
            commit_all(repo, snapshot["fingerprint"], "test: push")
            self.assertTrue(push_current(repo)["pushed"])
            remote_head = subprocess.run(
                ["git", "--git-dir", str(remote), "rev-parse", "refs/heads/main"],
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
            self.assertEqual(run(repo, "rev-parse", "HEAD").stdout.strip(), remote_head)

    def test_push_failure_preserves_local_commit(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo = Path(temp_dir)
            initialize(repo)
            before = run(repo, "rev-parse", "HEAD").stdout.strip()
            (repo / "tracked.txt").write_text("local\n", encoding="utf-8")
            snapshot = working_tree_snapshot(repo)
            result = commit_all(repo, snapshot["fingerprint"], "test: local")
            with self.assertRaises(GitOperationError) as caught:
                push_current(repo)
            self.assertEqual("push_failed", caught.exception.code)
            self.assertNotEqual(before, result["hash"])
            self.assertEqual(result["hash"], run(repo, "rev-parse", "HEAD").stdout.strip())
