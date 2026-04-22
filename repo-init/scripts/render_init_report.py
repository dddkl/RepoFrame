#!/usr/bin/env python3
"""Render a standard initialization report from intake, mode, and policy JSON."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from repo_init_common import load_json


def summarize_policy(policy_json: dict) -> dict[str, list[str]]:
    """Group files by policy."""
    grouped = {
        "create": [],
        "supplement": [],
        "preserve": [],
        "rewrite": [],
    }
    for target, details in policy_json.get("files", {}).items():
        grouped.setdefault(details["policy"], []).append(target)
    return grouped


def render_markdown(intake: dict, mode_json: dict, policy_json: dict, assumptions: list[str], extra_warnings: list[str]) -> str:
    """Render a markdown report."""
    grouped = summarize_policy(policy_json)
    warnings = [*intake.get("warnings", []), *extra_warnings]
    source_path = intake.get("source_path") or "prompt-only input"
    source_roles = intake.get("source_roles") or []
    conflicts = intake.get("conflicts") or []
    clarification_questions = intake.get("clarification_questions") or []
    adopted_defaults = intake.get("adopted_defaults") or []

    lines = [
        "# Initialization Report",
        "",
        f"- Mode: `{mode_json['mode']}`",
        f"- Primary source: `{intake.get('primary_source') or source_path}`",
        f"- Source count: `{intake.get('source_count', 0)}`",
        f"- Title: `{intake.get('title') or 'Untitled project input'}`",
        f"- Bundle confidence: `{intake.get('bundle_confidence', intake.get('confidence'))}`",
        "",
        "## Sources",
        "",
    ]
    if source_roles:
        lines.extend(
            [f"- `{item['label']}`: role=`{item['role']}`, confidence=`{item['confidence']}`" for item in source_roles]
        )
    else:
        lines.append(f"- `{source_path}`")

    lines.extend(
        [
            "",
            "## Planned File Actions",
            "",
            f"- Create: {', '.join(grouped['create']) or 'none'}",
            f"- Supplement: {', '.join(grouped['supplement']) or 'none'}",
            f"- Preserve: {', '.join(grouped['preserve']) or 'none'}",
            f"- Rewrite: {', '.join(grouped['rewrite']) or 'none'}",
            "",
            "## Assumptions",
            "",
        ]
    )
    if assumptions:
        lines.extend([f"- {item}" for item in assumptions])
    else:
        lines.append("- none")

    lines.extend(["", "## Adopted Defaults", ""])
    if adopted_defaults:
        lines.extend([f"- {item}" for item in adopted_defaults])
    else:
        lines.append("- none")

    lines.extend(["", "## Conflicts", ""])
    if conflicts:
        lines.extend([f"- `{item['field']}`: chose `{item['chosen_from']}` over `{item['discarded_from']}`" for item in conflicts])
    else:
        lines.append("- none")

    lines.extend(["", "## Clarification Questions", ""])
    if clarification_questions:
        lines.extend([f"- {item}" for item in clarification_questions])
    else:
        lines.append("- none")

    lines.extend(["", "## Warnings", ""])
    if warnings:
        lines.extend([f"- {item}" for item in warnings])
    else:
        lines.append("- none")
    return "\n".join(lines) + "\n"


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--intake", required=True, help="Path to normalized intake JSON.")
    parser.add_argument("--mode-json", required=True, help="Path to mode-classification JSON.")
    parser.add_argument("--policy-json", required=True, help="Path to write-policy JSON.")
    parser.add_argument("--assumption", action="append", default=[], help="Assumption to include.")
    parser.add_argument("--warning", action="append", default=[], help="Additional warning to include.")
    parser.add_argument("--format", choices=("markdown", "json"), default="markdown")
    parser.add_argument("--output", help="Optional output path.")
    return parser.parse_args()


def main() -> int:
    """Render the initialization report."""
    args = parse_args()
    try:
        intake = load_json(args.intake)
        mode_json = load_json(args.mode_json)
        policy_json = load_json(args.policy_json)
        grouped = summarize_policy(policy_json)

        if args.format == "json":
            payload = {
                "mode": mode_json["mode"],
                "source_files_used": [item["path"] for item in intake.get("source_roles", []) if item.get("path")],
                "primary_source": intake.get("primary_source"),
                "source_roles": intake.get("source_roles", []),
                "files_created": grouped["create"],
                "files_supplemented": grouped["supplement"],
                "files_preserved": grouped["preserve"],
                "files_rewritten": grouped["rewrite"],
                "assumptions": args.assumption,
                "adopted_defaults": intake.get("adopted_defaults", []),
                "conflicts": intake.get("conflicts", []),
                "clarification_questions": intake.get("clarification_questions", []),
                "bundle_confidence": intake.get("bundle_confidence", intake.get("confidence")),
                "warnings": [*intake.get("warnings", []), *args.warning],
            }
            text = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
        else:
            text = render_markdown(intake, mode_json, policy_json, args.assumption, args.warning)

        if args.output:
            output_path = Path(args.output)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with output_path.open("w", encoding="utf-8") as handle:
                handle.write(text)
        else:
            print(text, end="")
        return 0
    except Exception as exc:  # pragma: no cover - CLI entry point
        print(f"render_init_report.py: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
