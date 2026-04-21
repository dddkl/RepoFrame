#!/usr/bin/env python3
"""Classify repository initialization mode from normalized intake and repo state."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from repo_init_common import load_json, summarize_repo, write_json


def choose_mode(intake: dict, repo_summary: dict) -> tuple[str, list[str]]:
    """Choose greenfield, plan-ingest, or repo-hydrate."""
    reasons: list[str] = []
    if intake.get("source_type") == "file" and intake.get("source_path"):
        reasons.append("Authoritative source file was provided in the intake.")
        return "plan-ingest", reasons

    meaningful_content = (
        repo_summary["code_file_count"] > 0
        or repo_summary["partial_doc_count"] > 0
        or repo_summary["meaningful_file_count"] > 3
    )
    if meaningful_content:
        reasons.append("Repository already contains meaningful code or project documentation.")
        return "repo-hydrate", reasons

    reasons.append("No authoritative source file or established repository content was detected.")
    return "greenfield", reasons


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--intake", required=True, help="Path to normalized intake JSON.")
    parser.add_argument("--repo", required=True, help="Repository root to inspect.")
    parser.add_argument("--output", help="Optional path to write JSON output.")
    return parser.parse_args()


def main() -> int:
    """Run mode classification."""
    args = parse_args()
    try:
        repo_root = Path(args.repo).resolve()
        intake = load_json(args.intake)
        repo_summary = summarize_repo(repo_root)
        mode, reasons = choose_mode(intake, repo_summary)
        result = {
            "mode": mode,
            "reasons": reasons,
            "repo_summary": repo_summary,
        }
        write_json(result, args.output)
        return 0
    except Exception as exc:  # pragma: no cover - CLI entry point
        print(f"classify_init_mode.py: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
