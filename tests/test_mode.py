from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from repoframe.mode import ModeError, get_mode, get_provider, initialize_mode, is_git_repository, set_mode


def git_init(path: Path) -> None:
    subprocess.run(["git", "-C", str(path), "init"], check=True, capture_output=True)


class ModeTests(unittest.TestCase):
    def test_infers_mode_without_changing_worktree(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo = Path(temp_dir)
            git_init(repo)
            self.assertEqual("iteration", get_mode(repo))
            (repo / ".repoframe").mkdir()
            (repo / ".repoframe/state.json").write_text("{}", encoding="utf-8")
            self.assertEqual("long-run", get_mode(repo))

    def test_persists_mode_in_local_git_config(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo = Path(temp_dir)
            git_init(repo)
            set_mode(repo, "iteration")
            self.assertEqual("iteration", get_mode(repo))
            status = subprocess.run(
                ["git", "-C", str(repo), "status", "--porcelain"],
                check=True,
                capture_output=True,
                text=True,
            )
            self.assertEqual("", status.stdout)
            set_mode(repo, "long-run")
            self.assertEqual("long-run", get_mode(repo))

    def test_rejects_mode_write_outside_git_and_unknown_mode(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo = Path(temp_dir)
            self.assertFalse(is_git_repository(repo))
            with self.assertRaises(ModeError):
                set_mode(repo, "iteration")
            git_init(repo)
            with self.assertRaises(ModeError):
                set_mode(repo, "unknown")

    def test_provider_defaults_to_codex_and_can_be_configured(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo = Path(temp_dir)
            git_init(repo)
            self.assertEqual("codex", get_provider(repo))
            subprocess.run(
                ["git", "-C", str(repo), "config", "--local", "repoframe.agent-provider", "claude"],
                check=True,
            )
            self.assertEqual("claude", get_provider(repo))

    def test_initialize_mode_is_noop_outside_git(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            initialize_mode(Path(temp_dir), "iteration")
