#!/usr/bin/env python3
"""Plan per-file write policy for repository initialization."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from repo_init_common import classify_text_state, load_json, write_json


TARGETS = {
    "README.md": "README.md",
    "AGENT.md": "AGENT.md",
    "PROJECT.md": "PROJECT.md",
    "STATUS.md": "STATUS.md",
    "DECISIONS.md": "DECISIONS.md",
}


def policy_for_project(mode: str, state: str, rewrite_requested: bool) -> tuple[str, str]:
    """Choose policy for PROJECT.md."""
    if rewrite_requested:
        return "rewrite", "User explicitly requested project-document restructuring."
    if state == "missing":
        return "create", "PROJECT.md does not exist."
    if mode == "plan-ingest":
        if state in {"empty", "template"}:
            return "supplement", "Fill PROJECT.md as a compatibility layer without replacing the source plan."
        return "preserve", "Keep the existing project definition and preserve the authoritative source."
    if mode == "repo-hydrate":
        if state in {"empty", "template"}:
            return "supplement", "Hydrate PROJECT.md with repository context."
        return "preserve", "Preserve established project-definition content during hydration."
    if state in {"empty", "template"}:
        return "supplement", "Replace placeholder content with generated project definition."
    return "preserve", "Existing PROJECT.md already contains project-specific content."


def policy_for_general(target: str, state: str) -> tuple[str, str]:
    """Choose policy for general collaboration files."""
    if state == "missing":
        return "create", f"{target} does not exist."
    return "supplement", f"{target} already exists and should be updated compatibly."


def build_write_policy(repo_root: Path, mode: str, rewrite_project: bool = False) -> dict[str, dict[str, str]]:
    """Build per-file write policy for a repository root."""
    files: dict[str, dict[str, str]] = {}
    for target, relative_path in TARGETS.items():
        state = classify_text_state(repo_root / relative_path)
        if target == "PROJECT.md":
            policy, reason = policy_for_project(mode, state, rewrite_project)
        else:
            policy, reason = policy_for_general(target, state)
        files[target] = {
            "policy": policy,
            "state": state,
            "reason": reason,
        }

    tasks_dir = repo_root / "tasks"
    files["tasks/"] = {
        "policy": "create" if not tasks_dir.exists() else "supplement",
        "state": "missing" if not tasks_dir.exists() else "present",
        "reason": "Create the tasks directory if absent; otherwise add a real task file.",
    }
    return files


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode-json", required=True, help="Path to mode-classification JSON.")
    parser.add_argument("--repo", required=True, help="Repository root to inspect.")
    parser.add_argument(
        "--rewrite-project",
        action="store_true",
        help="Allow rewrite of PROJECT.md.",
    )
    parser.add_argument("--output", help="Optional path to write JSON output.")
    return parser.parse_args()


def main() -> int:
    """Run write-policy planning."""
    args = parse_args()
    try:
        repo_root = Path(args.repo).resolve()
        mode_json = load_json(args.mode_json)
        mode = mode_json["mode"]
        files = build_write_policy(repo_root, mode, args.rewrite_project)

        result = {
            "mode": mode,
            "files": files,
        }
        write_json(result, args.output)
        return 0
    except Exception as exc:  # pragma: no cover - CLI entry point
        print(f"plan_write_policy.py: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
