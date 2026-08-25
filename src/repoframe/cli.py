"""Command-line interface for RepoFrame."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence

from . import __version__
from .initialize import InitializationError, initialize
from .state import load_and_validate


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="repoframe", description="Visible, resumable execution state for coding agents.")
    parser.add_argument("--version", action="version", version=f"repoframe {__version__}")
    commands = parser.add_subparsers(dest="command", required=True)

    init_parser = commands.add_parser("init", help="Initialize or refresh RepoFrame in the current repository.")
    init_parser.add_argument("--goal", help="Goal title; required when creating new state.")
    init_parser.add_argument("--outcome", help="Desired outcome; defaults to the goal title.")
    init_parser.add_argument("--criterion", action="append", default=[], help="Success criterion; repeat as needed.")
    init_parser.add_argument("--constraint", action="append", default=[], help="Hard constraint; repeat as needed.")
    init_parser.add_argument(
        "--agents",
        default="auto",
        help="auto, all, none, or a comma-separated subset of codex,claude,gemini,cursor,copilot.",
    )

    validate_parser = commands.add_parser("validate", help="Validate .repoframe/state.json.")
    validate_parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON diagnostics.")

    view_parser = commands.add_parser("view", help="Open the local read-only DAG viewer.")
    view_parser.add_argument("--port", type=int, default=7331, help="Loopback port (default: 7331).")
    view_parser.add_argument("--no-open", action="store_true", help="Do not open the browser automatically.")
    return parser


def _run_init(args: argparse.Namespace, cwd: Path) -> int:
    if not (cwd / ".repoframe/state.json").exists() and (args.goal is None or not args.goal.strip()):
        print("repoframe init: --goal is required when creating new state.", file=sys.stderr)
        return 2
    try:
        changes = initialize(cwd, args.goal, args.outcome, args.criterion, args.constraint, args.agents)
    except InitializationError as exc:
        print(f"repoframe init: {exc}", file=sys.stderr)
        return 1
    print("RepoFrame initialized.")
    for change in changes:
        print(f"  {change.action:9} {change.path.as_posix()}")
    print("Next: update .repoframe/state.json, run 'repoframe validate', then 'repoframe view'.")
    return 0


def _run_validate(args: argparse.Namespace, cwd: Path) -> int:
    payload, _, issues = load_and_validate(cwd / ".repoframe/state.json")
    if args.json:
        print(json.dumps({"valid": not issues, "issues": [issue.to_dict() for issue in issues]}, indent=2))
    elif issues:
        for issue in issues:
            print(f"{issue.code} {issue.path}: {issue.message}", file=sys.stderr)
    else:
        assert payload is not None
        active = next((node["id"] for node in payload["nodes"] if node["status"] == "active"), "none")
        print(
            f"RepoFrame state is valid (schema v{payload['schema_version']}, "
            f"{len(payload['nodes'])} nodes, active: {active})."
        )
    return 1 if issues else 0


def main(argv: Sequence[str] | None = None, *, cwd: Path | None = None) -> int:
    """Run the RepoFrame CLI and return a process exit code."""
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return int(exc.code)
    root = (cwd or Path.cwd()).resolve()
    if args.command == "init":
        return _run_init(args, root)
    if args.command == "validate":
        return _run_validate(args, root)
    if args.command == "view":
        from .server import run_viewer

        return run_viewer(root, args.port, open_browser=not args.no_open)
    parser.error(f"Unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
