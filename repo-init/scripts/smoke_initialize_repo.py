#!/usr/bin/env python3
"""Run smoke validation for the repo-init initialization flow."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
INITIALIZER = SCRIPT_DIR / "initialize_repo.py"


def run_initializer(repo_path: Path, *args: str) -> dict:
    """Run initialize_repo.py and return its JSON payload."""
    command = [sys.executable, str(INITIALIZER), "--repo", str(repo_path), *args]
    completed = subprocess.run(command, capture_output=True, text=True)
    if completed.returncode != 0:
        raise AssertionError(
            "initialize_repo.py failed\n"
            f"command: {' '.join(command)}\n"
            f"stdout:\n{completed.stdout}\n"
            f"stderr:\n{completed.stderr}"
        )
    try:
        return json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise AssertionError(f"initialize_repo.py did not emit valid JSON:\n{completed.stdout}") from exc


def assert_contains(path: Path, required: list[str]) -> None:
    """Assert that a text file contains all required fragments."""
    text = path.read_text(encoding="utf-8")
    missing = [fragment for fragment in required if fragment not in text]
    if missing:
        raise AssertionError(f"{path} is missing expected fragments: {missing}")


def assert_artifacts_exist(repo_path: Path) -> None:
    """Assert that required artifact files exist."""
    artifacts_dir = repo_path / ".repo-init"
    for name in ("intake.json", "mode.json", "policy.json", "init-report.md"):
        path = artifacts_dir / name
        if not path.exists():
            raise AssertionError(f"Missing artifact: {path}")


def assert_report_contract(path: Path) -> None:
    """Assert that the initialization report exposes required source metadata."""
    assert_contains(path, ["- Source files used:", "## Source Roles"])


def validate_greenfield(base_dir: Path) -> None:
    """Validate prompt-only initialization."""
    repo_path = base_dir / "greenfield"
    repo_path.mkdir(parents=True, exist_ok=True)
    result = run_initializer(
        repo_path,
        "--prompt",
        "Initialize this repository as a TypeScript CLI called ReleasePilot for small release teams. The goal is to automate changelog preparation. Use Node.js, TypeScript, and Vitest. Do not build a web UI in the first phase.",
    )
    if result["mode"] != "greenfield":
        raise AssertionError(f"Expected greenfield mode, got {result['mode']}")
    assert_artifacts_exist(repo_path)
    assert_contains(repo_path / "REUSE.md", ["## When Required", "## Evaluation Criteria", "## Decision Options"])
    assert_contains(
        repo_path / "README.md",
        ["## Repository Purpose", "## Initialization Model", "## Collaboration Contract", "## Detailed Rules", "`REUSE.md`"],
    )
    assert_contains(repo_path / "STATUS.md", ["## Latest Feedback", "## Task Impact", "## Recommended Replan"])
    assert_report_contract(repo_path / ".repo-init" / "init-report.md")
    task_path = repo_path / "tasks" / result["task_decomposition"]["recommended_start_task"]
    assert_contains(task_path, ["## Assumption Checks", "## Downstream Impact", "## Open Source Reuse Check"])


def validate_plan_ingest_clarification(base_dir: Path) -> None:
    """Validate low-information plan-ingest initialization."""
    repo_path = base_dir / "clarify"
    repo_path.mkdir(parents=True, exist_ok=True)
    plan_path = repo_path / "plan.txt"
    plan_path.write_text("Prototype idea", encoding="utf-8")
    result = run_initializer(repo_path, "--source", str(plan_path))
    if result["mode"] != "plan-ingest":
        raise AssertionError(f"Expected plan-ingest mode, got {result['mode']}")
    assert_artifacts_exist(repo_path)
    assert_contains(repo_path / "REUSE.md", ["## When Required", "## Evaluation Criteria", "## Decision Options"])
    assert_contains(
        repo_path / "README.md",
        ["## Repository Purpose", "## Initialization Model", "## Collaboration Contract", "## Detailed Rules", "`REUSE.md`"],
    )
    assert_contains(repo_path / "STATUS.md", ["## Latest Feedback", "## Task Impact", "## Recommended Replan"])
    assert_report_contract(repo_path / ".repo-init" / "init-report.md")
    task_path = repo_path / "tasks" / result["task_decomposition"]["recommended_start_task"]
    assert_contains(task_path, ["## Assumption Checks", "## Downstream Impact", "## Open Source Reuse Check"])


def validate_repo_hydrate_complex(base_dir: Path) -> None:
    """Validate complex repo-hydrate initialization."""
    repo_path = base_dir / "hydrate"
    src_path = repo_path / "src"
    src_path.mkdir(parents=True, exist_ok=True)
    for index in range(1, 9):
        (src_path / f"module{index}.py").write_text(f"def fn{index}():\n    return {index}\n", encoding="utf-8")
    (repo_path / "README.md").write_text("# Existing Repo\n", encoding="utf-8")
    result = run_initializer(
        repo_path,
        "--prompt",
        "Use repo-init to add the collaboration layer to this existing repository without treating it as a greenfield project.",
    )
    if result["mode"] != "repo-hydrate":
        raise AssertionError(f"Expected repo-hydrate mode, got {result['mode']}")
    if not result["task_decomposition"]["applied"]:
        raise AssertionError("Expected task decomposition for complex repo-hydrate smoke test.")
    assert_artifacts_exist(repo_path)
    assert_contains(repo_path / "REUSE.md", ["## When Required", "## Evaluation Criteria", "## Decision Options"])
    assert_contains(
        repo_path / "README.md",
        ["## Collaboration Layer", "### Repository Purpose", "### Initialization Model", "### Detailed Rules", "`REUSE.md`"],
    )
    assert_contains(repo_path / "STATUS.md", ["## Latest Feedback", "## Task Impact", "## Recommended Replan"])
    assert_report_contract(repo_path / ".repo-init" / "init-report.md")
    master_task = repo_path / "tasks" / result["task_decomposition"]["master_task"]
    child_task = repo_path / "tasks" / result["task_decomposition"]["recommended_start_task"]
    assert_contains(master_task, ["## Replan Triggers", "## Feedback Ledger", "## Replan Decisions", "## Open Source Reuse Check"])
    assert_contains(child_task, ["## Assumption Checks", "## Downstream Impact", "## Open Source Reuse Check"])


def main() -> int:
    """Run all smoke scenarios."""
    try:
        with tempfile.TemporaryDirectory(prefix="repo-init-smoke-") as temp_dir:
            base_dir = Path(temp_dir)
            validate_greenfield(base_dir)
            validate_plan_ingest_clarification(base_dir)
            validate_repo_hydrate_complex(base_dir)
        print("smoke_initialize_repo.py: all scenarios passed")
        return 0
    except Exception as exc:  # pragma: no cover - CLI entry point
        print(f"smoke_initialize_repo.py: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
