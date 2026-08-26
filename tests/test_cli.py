from __future__ import annotations

import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from repoframe.cli import main


def invoke(arguments: list[str], cwd: Path) -> tuple[int, str, str]:
    stdout = io.StringIO()
    stderr = io.StringIO()
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        result = main(arguments, cwd=cwd)
    return result, stdout.getvalue(), stderr.getvalue()


class CliTests(unittest.TestCase):
    def test_init_creates_state_and_reports_changes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo = Path(temp_dir)
            code, stdout, stderr = invoke(
                [
                    "init",
                    "--goal",
                    "Ship auth",
                    "--criterion",
                    "Tests pass",
                    "--criterion",
                    "Review passes",
                    "--constraint",
                    "No SaaS",
                    "--agents",
                    "none",
                ],
                repo,
            )
            payload = json.loads((repo / ".repoframe/state.json").read_text(encoding="utf-8"))
        self.assertEqual(0, code, stderr)
        self.assertIn("RepoFrame initialized", stdout)
        self.assertEqual(["Tests pass", "Review passes"], payload["goal"]["success_criteria"])

    def test_init_without_goal_creates_iteration_setup(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo = Path(temp_dir)
            code, stdout, stderr = invoke(["init", "--agents", "none"], repo)
            state_exists = (repo / ".repoframe/state.json").exists()
            instructions_exist = (repo / ".repoframe/instructions.md").exists()
        self.assertEqual(0, code, stderr)
        self.assertFalse(state_exists)
        self.assertTrue(instructions_exist)
        self.assertIn("Iteration", stdout)

    def test_init_goal_fields_without_goal_are_usage_error(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            code, _, stderr = invoke(["init", "--criterion", "Tests pass"], Path(temp_dir))
        self.assertEqual(2, code)
        self.assertIn("--goal", stderr)

    def test_blank_goal_is_usage_error(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            code, _, stderr = invoke(["init", "--goal", "   "], Path(temp_dir))
        self.assertEqual(2, code)
        self.assertIn("cannot be empty", stderr)

    def test_validate_reports_valid_state(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo = Path(temp_dir)
            invoke(["init", "--goal", "Ship auth", "--agents", "none"], repo)
            code, stdout, stderr = invoke(["validate"], repo)
        self.assertEqual(0, code, stderr)
        self.assertIn("valid", stdout.lower())
        self.assertIn("0 nodes", stdout)

    def test_validate_json_reports_invalid_state(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo = Path(temp_dir)
            state_dir = repo / ".repoframe"
            state_dir.mkdir()
            (state_dir / "state.json").write_text("{", encoding="utf-8")
            code, stdout, _ = invoke(["validate", "--json"], repo)
            payload = json.loads(stdout)
        self.assertEqual(1, code)
        self.assertFalse(payload["valid"])
        self.assertEqual("json.invalid", payload["issues"][0]["code"])

    def test_validate_text_reports_issue_path(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo = Path(temp_dir)
            state_dir = repo / ".repoframe"
            state_dir.mkdir()
            (state_dir / "state.json").write_text("{}", encoding="utf-8")
            code, _, stderr = invoke(["validate"], repo)
        self.assertEqual(1, code)
        self.assertIn("schema.required", stderr)
        self.assertIn("$.", stderr)

    def test_version_is_available(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            code, stdout, stderr = invoke(["--version"], Path(temp_dir))
        self.assertEqual(0, code, stderr)
        self.assertEqual("repoframe 0.2.0", stdout.strip())


if __name__ == "__main__":
    unittest.main()
