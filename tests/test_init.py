from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from repoframe.initialize import InitializationError, initialize
from repoframe.state import load_and_validate


class InitializationTests(unittest.TestCase):
    def test_git_initialization_sets_repository_local_mode_without_dirty_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo = Path(temp_dir)
            subprocess.run(["git", "-C", str(repo), "init"], check=True, capture_output=True)
            initialize(repo, None, None, [], [], "none")
            mode = subprocess.run(
                ["git", "-C", str(repo), "config", "--local", "--get", "repoframe.mode"],
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
            self.assertEqual("iteration", mode)
            initialize(repo, "Ship auth", None, [], [], "none")
            mode = subprocess.run(
                ["git", "-C", str(repo), "config", "--local", "--get", "repoframe.mode"],
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
            self.assertEqual("long-run", mode)

    def test_initializes_core_files_and_falls_back_to_agents(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo = Path(temp_dir)
            changes = initialize(repo, "Ship auth", None, ["Tests pass"], ["No SaaS"], "auto")
            payload = json.loads((repo / ".repoframe/state.json").read_text(encoding="utf-8"))
            _, _, issues = load_and_validate(repo / ".repoframe/state.json")

            self.assertEqual([], issues)
            self.assertEqual("Ship auth", payload["goal"]["outcome"])
            self.assertEqual(["Tests pass"], payload["goal"]["success_criteria"])
            self.assertTrue((repo / ".repoframe/state.schema.json").exists())
            self.assertTrue((repo / ".repoframe/instructions.md").exists())
            self.assertTrue((repo / "AGENTS.md").exists())
            instructions = (repo / ".repoframe/instructions.md").read_text(encoding="utf-8")
            self.assertIn("Do not create, read, or update execution state", instructions)
            self.assertIn("Long Run", instructions)
            self.assertEqual(2, payload["schema_version"])
            self.assertIn("created", {change.action for change in changes})

    def test_none_does_not_create_agent_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo = Path(temp_dir)
            initialize(repo, "Ship auth", None, [], [], "none")
            self.assertFalse((repo / "AGENTS.md").exists())
            self.assertFalse((repo / "CLAUDE.md").exists())

    def test_all_creates_four_unique_instruction_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo = Path(temp_dir)
            initialize(repo, "Ship auth", None, [], [], "all")
            paths = [
                repo / "AGENTS.md",
                repo / "CLAUDE.md",
                repo / "GEMINI.md",
                repo / ".github/copilot-instructions.md",
            ]
            for path in paths:
                self.assertTrue(path.exists(), path)
                self.assertEqual(1, path.read_text(encoding="utf-8").count("<!-- repoframe:start -->"))

    def test_auto_detects_existing_instruction_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo = Path(temp_dir)
            (repo / "CLAUDE.md").write_text("# Claude\n", encoding="utf-8")
            (repo / "GEMINI.md").write_text("# Gemini\n", encoding="utf-8")
            initialize(repo, "Ship auth", None, [], [], "auto")
            self.assertIn("RepoFrame", (repo / "CLAUDE.md").read_text(encoding="utf-8"))
            self.assertIn("RepoFrame", (repo / "GEMINI.md").read_text(encoding="utf-8"))
            self.assertFalse((repo / "AGENTS.md").exists())

    def test_explicit_codex_and_cursor_only_write_agents_once(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo = Path(temp_dir)
            initialize(repo, "Ship auth", None, [], [], "codex,cursor")
            text = (repo / "AGENTS.md").read_text(encoding="utf-8")
            self.assertEqual(1, text.count("<!-- repoframe:start -->"))

    def test_preserves_user_content_and_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo = Path(temp_dir)
            original = "# Existing instructions\n\nKeep this exactly.\n"
            (repo / "AGENTS.md").write_text(original, encoding="utf-8")
            initialize(repo, "Ship auth", None, [], [], "auto")
            first = (repo / "AGENTS.md").read_text(encoding="utf-8")
            initialize(repo, None, None, [], [], "auto")
            second = (repo / "AGENTS.md").read_text(encoding="utf-8")
            self.assertTrue(first.startswith(original))
            self.assertEqual(first, second)

    def test_existing_state_is_preserved(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo = Path(temp_dir)
            initialize(repo, "Ship auth", None, [], [], "none")
            state_path = repo / ".repoframe/state.json"
            original = state_path.read_bytes()
            initialize(repo, "Ship auth", "Different outcome", ["new"], ["new"], "none")
            self.assertEqual(original, state_path.read_bytes())

    def test_different_goal_cannot_replace_existing_state(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo = Path(temp_dir)
            initialize(repo, "Ship auth", None, [], [], "none")
            with self.assertRaisesRegex(InitializationError, "different goal"):
                initialize(repo, "Ship billing", None, [], [], "none")

    def test_iteration_initialization_does_not_create_state(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo = Path(temp_dir)
            changes = initialize(repo, None, None, [], [], "none")
            self.assertFalse((repo / ".repoframe/state.json").exists())
            self.assertTrue((repo / ".repoframe/state.schema.json").exists())
            self.assertTrue((repo / ".repoframe/instructions.md").exists())
            self.assertNotIn(Path(".repoframe/state.json"), [change.path for change in changes])

    def test_iteration_rejects_goal_fields_without_goal(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            with self.assertRaisesRegex(InitializationError, "--goal"):
                initialize(Path(temp_dir), None, "Outcome", [], [], "none")

    def test_blank_goal_is_not_treated_as_iteration(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            with self.assertRaisesRegex(InitializationError, "cannot be empty"):
                initialize(Path(temp_dir), "   ", None, [], [], "none")

    def test_malformed_managed_markers_prevent_all_writes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo = Path(temp_dir)
            claude = repo / "CLAUDE.md"
            claude.write_text("<!-- repoframe:start -->\nbroken\n", encoding="utf-8")
            with self.assertRaisesRegex(InitializationError, "managed markers"):
                initialize(repo, "Ship auth", None, [], [], "all")
            self.assertFalse((repo / ".repoframe").exists())
            self.assertEqual("<!-- repoframe:start -->\nbroken\n", claude.read_text(encoding="utf-8"))

    def test_duplicate_managed_blocks_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo = Path(temp_dir)
            block = "<!-- repoframe:start -->\nx\n<!-- repoframe:end -->\n"
            (repo / "AGENTS.md").write_text(block + block, encoding="utf-8")
            with self.assertRaises(InitializationError):
                initialize(repo, "Ship auth", None, [], [], "auto")
            self.assertFalse((repo / ".repoframe").exists())

    def test_reversed_managed_markers_are_rejected_cleanly(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo = Path(temp_dir)
            (repo / "AGENTS.md").write_text(
                "<!-- repoframe:end -->\ntext\n<!-- repoframe:start -->\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(InitializationError, "managed markers"):
                initialize(repo, "Ship auth", None, [], [], "auto")
            self.assertFalse((repo / ".repoframe").exists())

    def test_invalid_agent_selection_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            with self.assertRaisesRegex(InitializationError, "Unknown agent"):
                initialize(Path(temp_dir), "Ship auth", None, [], [], "codex,unknown")

    def test_invalid_goal_fields_are_rejected_before_writing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo = Path(temp_dir)
            with self.assertRaisesRegex(InitializationError, "invalid"):
                initialize(repo, "Ship auth", "   ", [""], [], "none")
            self.assertFalse((repo / ".repoframe").exists())

    def test_write_failure_rolls_back_applied_files_and_user_content(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo = Path(temp_dir)
            agents_path = repo / "AGENTS.md"
            original = b"# User instructions\n"
            agents_path.write_bytes(original)
            from repoframe import initialize as initialize_module

            real_replace = initialize_module.os.replace
            calls = 0

            def fail_after_agent_update(source: object, target: object) -> None:
                nonlocal calls
                calls += 1
                if calls == 5:
                    raise OSError("simulated write failure")
                real_replace(source, target)

            with patch("repoframe.initialize.os.replace", side_effect=fail_after_agent_update):
                with self.assertRaisesRegex(InitializationError, "atomically"):
                    initialize(repo, "Ship auth", None, [], [], "all")

            self.assertEqual(original, agents_path.read_bytes())
            self.assertFalse((repo / ".repoframe/state.json").exists())
            self.assertFalse(any(repo.rglob("*.tmp")))

    def test_managed_directory_symlink_cannot_escape_repository(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            repo = root / "repo"
            outside = root / "outside"
            repo.mkdir()
            outside.mkdir()
            try:
                os.symlink(outside, repo / ".repoframe", target_is_directory=True)
            except OSError as exc:
                self.skipTest(f"Directory symlinks are unavailable: {exc}")
            with self.assertRaisesRegex(InitializationError, "outside the repository"):
                initialize(repo, "Ship auth", None, [], [], "none")
            self.assertEqual([], list(outside.iterdir()))


if __name__ == "__main__":
    unittest.main()
