#!/usr/bin/env python3
"""Lint RepoFrame acceptance.json milestone checks."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


def load_json(path: Path) -> dict[str, Any]:
    """Load a JSON object from disk."""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"{path} is not valid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object.")
    return payload


def dot_path_value(payload: Any, dotted_path: str) -> Any:
    """Read a simple dot-separated path from a JSON object."""
    value = payload
    for part in dotted_path.split("."):
        if isinstance(value, dict) and part in value:
            value = value[part]
            continue
        raise KeyError(dotted_path)
    return value


def check_files_exist(repo_root: Path, check: dict[str, Any]) -> list[str]:
    """Return failures for missing files."""
    return [f"missing {path}" for path in check.get("paths", []) if not (repo_root / path).exists()]


def check_files_absent(repo_root: Path, check: dict[str, Any]) -> list[str]:
    """Return failures for files that should be absent."""
    return [f"unexpected {path}" for path in check.get("paths", []) if (repo_root / path).exists()]


def check_required_text(repo_root: Path, check: dict[str, Any]) -> list[str]:
    """Return failures for missing required text."""
    failures: list[str] = []
    patterns = check.get("patterns", [])
    for path in check.get("paths", []):
        target = repo_root / path
        if not target.exists():
            failures.append(f"missing {path}")
            continue
        text = target.read_text(encoding="utf-8", errors="replace")
        for pattern in patterns:
            if pattern not in text:
                failures.append(f"{path} missing {pattern!r}")
    return failures


def check_forbidden_text(repo_root: Path, check: dict[str, Any]) -> list[str]:
    """Return failures for present forbidden text."""
    failures: list[str] = []
    patterns = check.get("patterns", [])
    for path in check.get("paths", []):
        target = repo_root / path
        if not target.exists():
            failures.append(f"missing {path}")
            continue
        text = target.read_text(encoding="utf-8", errors="replace")
        for pattern in patterns:
            if pattern in text:
                failures.append(f"{path} contains forbidden {pattern!r}")
    return failures


def check_markdown_headings(repo_root: Path, check: dict[str, Any]) -> list[str]:
    """Return failures for missing markdown headings."""
    failures: list[str] = []
    headings = check.get("headings", [])
    for path in check.get("paths", []):
        target = repo_root / path
        if not target.exists():
            failures.append(f"missing {path}")
            continue
        text = target.read_text(encoding="utf-8", errors="replace")
        for heading in headings:
            if f"## {heading}" not in text and f"# {heading}" not in text:
                failures.append(f"{path} missing heading {heading!r}")
    return failures


def check_json_path_equals(repo_root: Path, check: dict[str, Any]) -> list[str]:
    """Return failures for simple JSON path equality checks."""
    path = check.get("path")
    dotted_path = check.get("json_path")
    expected = check.get("expected")
    if not path or not dotted_path:
        return ["json_path_equals requires path and json_path"]
    target = repo_root / path
    if not target.exists():
        return [f"missing {path}"]
    payload = load_json(target)
    try:
        actual = dot_path_value(payload, dotted_path)
    except KeyError:
        return [f"{path} missing JSON path {dotted_path!r}"]
    if actual != expected:
        return [f"{path} {dotted_path!r} expected {expected!r}, got {actual!r}"]
    return []


def check_command(repo_root: Path, check: dict[str, Any], allow_command_checks: bool) -> list[str]:
    """Return failures for a command check."""
    command = check.get("command")
    if not command:
        return ["command check requires command"]
    if not allow_command_checks:
        return ["command checks are disabled; rerun with --allow-command-checks"]
    completed = subprocess.run(command, cwd=repo_root, shell=True, capture_output=True, text=True)
    if completed.returncode == 0:
        return []
    detail = (completed.stderr or completed.stdout).strip().splitlines()
    suffix = f": {detail[0]}" if detail else ""
    return [f"command exited {completed.returncode}{suffix}"]


def run_check(repo_root: Path, check: dict[str, Any], allow_command_checks: bool) -> list[str]:
    """Run one acceptance check and return failure messages."""
    check_type = check.get("type")
    if check_type == "files_exist":
        return check_files_exist(repo_root, check)
    if check_type == "files_absent":
        return check_files_absent(repo_root, check)
    if check_type == "required_text":
        return check_required_text(repo_root, check)
    if check_type == "forbidden_text":
        return check_forbidden_text(repo_root, check)
    if check_type == "markdown_headings":
        return check_markdown_headings(repo_root, check)
    if check_type == "json_path_equals":
        return check_json_path_equals(repo_root, check)
    if check_type == "command":
        return check_command(repo_root, check, allow_command_checks)
    return [f"unknown check type {check_type!r}"]


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", default=".", help="Repository root.")
    parser.add_argument("--acceptance", default="acceptance.json", help="Acceptance JSON path relative to repo.")
    parser.add_argument("--allow-command-checks", action="store_true", help="Allow command checks to execute.")
    return parser.parse_args()


def main() -> int:
    """Run acceptance linting."""
    args = parse_args()
    try:
        repo_root = Path(args.repo).resolve()
        acceptance_path = repo_root / args.acceptance
        acceptance = load_json(acceptance_path)
        failures = 0
        for goal in acceptance.get("goals", []):
            goal_id = goal.get("id", "unknown-goal")
            goal_status = goal.get("status", "unknown")
            print(f"{goal_id} {goal_status}")
            for check in goal.get("checks", []):
                check_id = check.get("id", "unnamed-check")
                check_type = check.get("type", "unknown")
                check_failures = run_check(repo_root, check, args.allow_command_checks)
                if check_failures:
                    failures += len(check_failures)
                    for failure in check_failures:
                        print(f"FAIL {check_type} {check_id}: {failure}")
                else:
                    print(f"PASS {check_type} {check_id}")
        return 1 if failures else 0
    except Exception as exc:  # pragma: no cover - CLI entry point
        print(f"lint_acceptance.py: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
