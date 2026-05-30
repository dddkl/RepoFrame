#!/usr/bin/env python3
"""Run the deterministic end-to-end repo initialization flow."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

from build_source_bundle import build_source_bundle
from classify_init_mode import choose_mode
from init_output import apply_outputs
from init_render import (
    render_agent,
    render_agent_docs,
    render_acceptance,
    render_decisions,
    render_project,
    render_readme,
    render_readme_supplement,
    render_status,
)
from init_summary import detect_repo_hydrate_clarifications, low_confidence, merged_summary
from init_task_plan import assess_complexity, render_task_set
from plan_write_policy import build_write_policy
from render_init_report import render_markdown
from repo_init_common import DEFAULT_ARTIFACT_DIRNAME, summarize_repo, unique, write_json


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", required=True, help="Target repository root to initialize.")
    prompt_group = parser.add_mutually_exclusive_group()
    prompt_group.add_argument("--prompt", help="Prompt text for greenfield or hydrate initialization.")
    prompt_group.add_argument("--prompt-file", help="Path to a text file containing the prompt.")
    parser.add_argument("--source", action="append", default=[], help="Path to a project-plan file. Repeat as needed.")
    parser.add_argument("--primary-source", help="Optional authoritative source path.")
    parser.add_argument("--artifacts-dir", help="Optional override for the artifact directory.")
    parser.add_argument("--report-path", help="Optional override for the init report path.")
    parser.add_argument("--rewrite-project", action="store_true", help="Allow rewriting PROJECT.md.")
    parser.add_argument("--cleanup-artifacts", action="store_true", help="Remove the artifact directory after writing the report.")
    return parser.parse_args()


def load_prompt(args: argparse.Namespace) -> str:
    """Load prompt text from args."""
    if args.prompt:
        return args.prompt
    if args.prompt_file:
        return Path(args.prompt_file).read_text(encoding="utf-8")
    return ""


def select_artifacts_dir(repo_root: Path, requested: str | None) -> Path:
    """Choose the artifact directory."""
    if requested:
        return Path(requested).resolve()
    return repo_root / DEFAULT_ARTIFACT_DIRNAME


def main() -> int:
    """Run end-to-end repository initialization."""
    args = parse_args()
    try:
        if not args.prompt and not args.prompt_file and not args.source:
            raise ValueError("Provide at least one of --prompt, --prompt-file, or --source.")

        repo_root = Path(args.repo).resolve()
        repo_root.mkdir(parents=True, exist_ok=True)
        artifacts_dir = select_artifacts_dir(repo_root, args.artifacts_dir)
        artifacts_dir.mkdir(parents=True, exist_ok=True)

        prompt_text = load_prompt(args)
        raw_bundle = build_source_bundle(repo_root, artifacts_dir, prompt_text, args.source, args.primary_source)

        repo_summary = summarize_repo(repo_root)
        mode, reasons = choose_mode(raw_bundle, repo_summary)

        intake = dict(raw_bundle)
        if mode == "repo-hydrate":
            questions, hydrate_warnings = detect_repo_hydrate_clarifications(repo_root, intake)
            intake["clarification_questions"] = unique([*(intake.get("clarification_questions") or []), *questions])
            intake["warnings"] = unique([*(intake.get("warnings") or []), *hydrate_warnings])
            if intake.get("source_type") == "prompt" and not intake.get("source_count", 0):
                intake["clarification_questions"] = [
                    question
                    for question in intake.get("clarification_questions") or []
                    if question != "The project goal is still unclear. Confirm the primary outcome before implementation proceeds."
                ]

        complexity_assessment, adaptive_task_planning = assess_complexity(mode, intake, repo_summary)
        intake["complexity_assessment"] = complexity_assessment
        intake["adaptive_task_planning"] = adaptive_task_planning
        intake["task_decomposition"] = {
            "applied": adaptive_task_planning.get("multi_task", False),
            "reason": adaptive_task_planning.get("reason"),
        }

        write_json(raw_bundle, str(artifacts_dir / "raw-intake.json"))

        mode_json = {
            "mode": mode,
            "reasons": reasons,
            "repo_summary": repo_summary,
        }
        write_json(mode_json, str(artifacts_dir / "mode.json"))

        policy_json = {
            "mode": mode,
            "files": build_write_policy(repo_root, mode, args.rewrite_project),
        }
        write_json(policy_json, str(artifacts_dir / "policy.json"))

        summary = merged_summary(intake, repo_root, mode)
        task_plan = render_task_set(repo_root, mode, intake, repo_summary, summary)
        intake["adaptive_task_planning"] = {
            **adaptive_task_planning,
            "goal_file": task_plan["goal_file"],
            "milestone_goals": task_plan["milestone_goals"],
            "active_goal": task_plan["active_goal"],
            "active_task": task_plan["active_task"],
            "planned_tasks": task_plan["planned_tasks"],
            "acceptance_file": task_plan["acceptance_file"],
            "recommended_start_task": task_plan["recommended_start_task"],
            "task_count": len(task_plan["planned_tasks"]),
        }
        intake["task_decomposition"] = {
            "applied": task_plan["decomposition_applied"],
            "reason": adaptive_task_planning.get("reason"),
            "master_task": task_plan["master_task"],
            "child_tasks": task_plan["child_tasks"],
            "recommended_start_task": task_plan["recommended_start_task"],
            "goal_file": task_plan["goal_file"],
            "milestone_goals": task_plan["milestone_goals"],
            "planned_tasks": task_plan["planned_tasks"],
        }
        write_json(intake, str(artifacts_dir / "intake.json"))

        content_map = {
            "README.md": render_readme(repo_root, mode, intake, summary),
            "AGENT.md": render_agent(mode, intake),
            "PROJECT.md": render_project(repo_root, mode, intake, summary),
            "STATUS.md": render_status(mode, intake, summary, task_plan),
            "DECISIONS.md": render_decisions(),
        }
        file_changes = apply_outputs(
            repo_root,
            policy_json,
            content_map,
            task_plan,
            render_readme_supplement(mode, intake, summary),
            render_agent_docs(),
            render_acceptance(task_plan),
        )

        report_path = Path(args.report_path).resolve() if args.report_path else artifacts_dir / "init-report.md"
        assumptions = unique(
            [
                *(intake.get("merged_snapshot", {}).get("assumptions") or []),
                *(
                    ["Initialization was kept conservative because the source bundle confidence is low."]
                    if low_confidence(intake)
                    else []
                ),
                *(
                    ["Initialization continued with unresolved clarification questions recorded in the workspace."]
                    if intake.get("clarification_questions")
                    else []
                ),
            ]
        )
        report_text = render_markdown(intake, mode_json, policy_json, assumptions, [])
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(report_text, encoding="utf-8")

        result = {
            "mode": mode,
            "repo": str(repo_root),
            "artifacts_dir": str(artifacts_dir),
            "report_path": str(report_path),
            "source_count": intake.get("source_count", 0),
            "primary_source": intake.get("primary_source"),
            "clarification_questions": intake.get("clarification_questions", []),
            "complexity_assessment": intake.get("complexity_assessment", {}),
            "adaptive_task_planning": intake.get("adaptive_task_planning", {}),
            "task_decomposition": intake.get("task_decomposition", {}),
            "goal_file": task_plan["goal_file"],
            "milestone_goals": task_plan["milestone_goals"],
            "active_goal": task_plan["active_goal"],
            "active_task": task_plan["active_task"],
            "planned_tasks": task_plan["planned_tasks"],
            "acceptance_file": task_plan["acceptance_file"],
            "recommended_start_task": task_plan["recommended_start_task"],
            "file_changes": file_changes,
        }
        print(json.dumps(result, indent=2, ensure_ascii=False))

        if args.cleanup_artifacts:
            if report_path.is_relative_to(artifacts_dir):
                raise RuntimeError("Cannot clean up artifacts when the report path is inside the artifact directory.")
            shutil.rmtree(artifacts_dir)
        return 0
    except Exception as exc:  # pragma: no cover - CLI entry point
        print(f"initialize_repo.py: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
