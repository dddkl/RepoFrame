from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from repoframe.git_inspect import GitInspectionError, inspect_repository


def git(repo: Path, *arguments: str) -> None:
    subprocess.run(["git", "-C", str(repo), *arguments], check=True, capture_output=True)


class GitInspectionTests(unittest.TestCase):
    def make_repository(self, repo: Path) -> None:
        git(repo, "init")
        git(repo, "config", "user.name", "RepoFrame Test")
        git(repo, "config", "user.email", "repoframe@example.test")
        (repo / "tracked.txt").write_text("first\n", encoding="utf-8")
        git(repo, "add", "tracked.txt")
        git(repo, "commit", "-m", "Initial snapshot")

    def test_reads_working_changes_and_commit_activity(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo = Path(temp_dir)
            self.make_repository(repo)
            (repo / "tracked.txt").write_text("first\nsecond\n", encoding="utf-8")
            (repo / "staged.txt").write_text("staged\n", encoding="utf-8")
            git(repo, "add", "staged.txt")
            (repo / "untracked.txt").write_text("untracked\n", encoding="utf-8")

            payload = inspect_repository(repo)

        self.assertFalse(payload["clean"])
        self.assertEqual(3, payload["working_changes"]["changed_files"])
        self.assertEqual(1, payload["working_changes"]["staged_files"])
        self.assertEqual(1, payload["working_changes"]["untracked_files"])
        self.assertGreaterEqual(payload["working_changes"]["additions"], 2)
        statuses = {item["path"]: item["status"] for item in payload["working_changes"]["files"]}
        self.assertEqual("modified", statuses["tracked.txt"])
        self.assertEqual("added", statuses["staged.txt"])
        self.assertEqual("untracked", statuses["untracked.txt"])
        self.assertEqual("Initial snapshot", payload["latest_commit"]["subject"])
        self.assertEqual(payload["latest_commit"], payload["recent_commits"][0])

    def test_clean_repository_has_no_working_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo = Path(temp_dir)
            self.make_repository(repo)
            payload = inspect_repository(repo)
        self.assertTrue(payload["clean"])
        self.assertEqual([], payload["working_changes"]["files"])

    def test_unborn_repository_has_no_latest_commit(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo = Path(temp_dir)
            git(repo, "init")
            payload = inspect_repository(repo)
        self.assertTrue(payload["branch"])
        self.assertIsNone(payload["latest_commit"])
        self.assertEqual([], payload["recent_commits"])

    def test_rename_preserves_current_and_original_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo = Path(temp_dir)
            self.make_repository(repo)
            git(repo, "mv", "tracked.txt", "renamed.txt")
            payload = inspect_repository(repo)
        renamed = payload["working_changes"]["files"][0]
        self.assertEqual("renamed", renamed["status"])
        self.assertEqual("renamed.txt", renamed["path"])
        self.assertEqual("tracked.txt", renamed["original_path"])

    def test_non_repository_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            with self.assertRaisesRegex(GitInspectionError, "not inside"):
                inspect_repository(Path(temp_dir))


if __name__ == "__main__":
    unittest.main()
