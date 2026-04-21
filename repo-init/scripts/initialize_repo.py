#!/usr/bin/env python3
"""Run the deterministic end-to-end repo initialization flow."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from pathlib import Path

from classify_init_mode import choose_mode
from doctor import collect_runtime_status
from extract_project_source import extract_from_path, extract_prompt
from normalize_project_intake import normalize_intake
from plan_write_policy import build_write_policy
from render_init_report import render_markdown
from repo_init_common import (
    DEFAULT_ARTIFACT_DIRNAME,
    MANAGED_MARKER,
    classify_text_state,
    first_non_empty_line,
    normalize_text,
    slugify,
    summarize_repo,
    unique,
    write_json,
)


TARGET_FILES = ("README.md", "AGENT.md", "PROJECT.md", "STATUS.md", "DECISIONS.md")


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", required=True, help="Target repository root to initialize.")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--prompt", help="Prompt text for greenfield or hydrate initialization.")
    source.add_argument("--prompt-file", help="Path to a text file containing the prompt.")
    source.add_argument("--source", help="Path to a project-plan file.")
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
    raise ValueError("Prompt text was not provided.")


def select_artifacts_dir(repo_root: Path, requested: str | None) -> Path:
    """Choose the artifact directory."""
    if requested:
        return Path(requested).resolve()
    return repo_root / DEFAULT_ARTIFACT_DIRNAME


def collect_source_inputs(args: argparse.Namespace, repo_root: Path, artifacts_dir: Path) -> tuple[dict, dict]:
    """Run extraction and normalization."""
    if args.source:
        source_path = Path(args.source).resolve()
        runtime = collect_runtime_status(str(source_path), [])
        if not runtime["ok"]:
            checks = [check["message"] for check in runtime["checks"] if not check["ok"]]
            raise RuntimeError(
                "Runtime is missing required dependencies. "
                + " ".join(checks or [f"Use Python {runtime['minimum_python_version']}+"])
                + f" Install with `{runtime['install_hint']}`."
            )
        raw = extract_from_path(source_path)
        extracted_text_output = artifacts_dir / f"{source_path.stem}.extracted.md"
    else:
        raw = extract_prompt(load_prompt(args))
        extracted_text_output = None

    normalized = normalize_intake(raw, str(extracted_text_output) if extracted_text_output else None)
    return raw, normalized


def split_sentences(text: str) -> list[str]:
    """Split text into simple sentences."""
    normalized = normalize_text(text)
    if not normalized:
        return []
    return [part.strip() for part in re.split(r"(?<=[.!?])\s+", normalized) if part.strip()]


def find_section(text: str, names: list[str]) -> str:
    """Find a markdown-like or plain-text section."""
    lowered = {name.lower() for name in names}
    lines = text.splitlines()
    for index, line in enumerate(lines):
        stripped = line.strip()
        candidate = stripped.lstrip("#").strip().rstrip(":").lower()
        if candidate in lowered:
            collected: list[str] = []
            for follow in lines[index + 1 :]:
                next_line = follow.strip()
                if not next_line:
                    if collected:
                        break
                    continue
                next_candidate = next_line.lstrip("#").strip().rstrip(":").lower()
                if next_candidate in lowered:
                    break
                if next_line.startswith("#") and collected:
                    break
                if next_line.rstrip(":").lower() in lowered and collected:
                    break
                collected.append(next_line)
            return normalize_text("\n".join(collected))
    return ""


def split_stack_items(text: str) -> list[str]:
    """Split a stack sentence or section into items."""
    raw = text.replace("\n", ", ")
    raw = raw.replace(" and ", ", ")
    items = [item.strip(" -") for item in raw.split(",")]
    return unique([item for item in items if item])


def infer_project_name(intake: dict, text: str, repo_root: Path) -> str:
    """Infer a project name."""
    patterns = [
        r"\bcalled\s+([A-Z][A-Za-z0-9_-]+)",
        r"\bnamed\s+([A-Z][A-Za-z0-9_-]+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return match.group(1)
    title = intake.get("title") or ""
    if title and title.lower() not in {"prompt input", "project-plan", "untitled project input"}:
        cleaned = re.sub(r"\b(html|docx|pdf)\b.*$", "", str(title), flags=re.IGNORECASE).strip(" -")
        if cleaned:
            return cleaned
    return repo_root.name or "Project"


def infer_greenfield_fields(intake: dict, repo_root: Path) -> dict:
    """Infer structured fields from prompt input."""
    text = intake["extracted_text"]
    sentences = split_sentences(text)
    name = infer_project_name(intake, text, repo_root)
    project_type = "project"
    type_match = re.search(r"initialize this repository as (?:an?|the)\s+(.+?)(?:\s+called|\s+named|\.|,|\n)", text, re.IGNORECASE)
    if type_match:
        project_type = type_match.group(1).strip()

    stage_match = re.search(r"stage is\s+([A-Za-z0-9-]+)", text, re.IGNORECASE)
    stage = stage_match.group(1).lower() if stage_match else "prototype"

    goal = ""
    goal_match = re.search(r"goal is to\s+(.+?)(?:[.\n]|$)", text, re.IGNORECASE)
    if goal_match:
        goal = goal_match.group(1).strip()
    elif len(sentences) > 1:
        goal = sentences[1].rstrip(".")
    else:
        goal = "Clarify the primary project outcome."

    stack_match = re.search(r"\buse\s+(.+?)(?:[.\n]|$)", text, re.IGNORECASE)
    stack = split_stack_items(stack_match.group(1)) if stack_match else []

    non_goals = [sentence.rstrip(".") for sentence in sentences if sentence.lower().startswith("do not ")]
    constraints = []
    if stack:
        constraints.append("Use " + ", ".join(stack) + ".")
    constraints.extend(non_goals)
    if "local-first" in text.lower():
        constraints.append("Keep the workflow local-first.")

    return {
        "name": name,
        "project_type": project_type,
        "stage": stage,
        "goal": goal.rstrip("."),
        "stack": stack,
        "constraints": unique(constraints),
        "assumptions": [
            "The repository starts empty enough for the collaboration layer to define the initial working structure.",
            "The brief is sufficient to start implementation planning without a separate full product specification.",
        ],
    }


def infer_plan_snapshot(intake: dict, repo_root: Path) -> dict:
    """Infer a safe project snapshot from plan-ingest input."""
    text = intake["extracted_text"]
    goal = find_section(text, ["goal", "primary goal"])
    users = find_section(text, ["users", "target users"])
    stack = find_section(text, ["stack", "tech stack", "technology stack"])
    constraints = find_section(text, ["constraints"])

    stack_items = split_stack_items(stack) if stack else []
    constraint_lines = unique([line.strip("- ") for line in constraints.splitlines() if line.strip()]) if constraints else []

    return {
        "name": infer_project_name(intake, text, repo_root),
        "goal": goal.rstrip(".") if goal else "",
        "users": users.rstrip(".") if users else "",
        "stack": stack_items,
        "constraints": constraint_lines,
        "assumptions": [
            "The provided source document remains the authoritative project definition unless the user asks for a rewrite.",
        ],
    }


def low_confidence(intake: dict) -> bool:
    """Return True when intake should be handled conservatively."""
    return intake.get("confidence", 0) < 0.5 or not intake.get("extracted_text", "").strip()


def choose_task(repo_root: Path, mode: str, intake: dict) -> tuple[str, str]:
    """Choose task filename slug and title."""
    existing_ids = [0]
    tasks_dir = repo_root / "tasks"
    if tasks_dir.exists():
        for path in tasks_dir.glob("TASK-*.md"):
            match = re.match(r"TASK-(\d+)", path.name)
            if match:
                existing_ids.append(int(match.group(1)))
    task_number = max(existing_ids) + 1
    prefix = f"TASK-{task_number:03d}"

    if mode == "greenfield":
        title = "Bootstrap initial project scaffold"
    elif mode == "repo-hydrate":
        title = "Align existing repository with collaboration workflow"
    elif low_confidence(intake):
        title = "Clarify source plan and recover missing scope"
    else:
        title = "Clarify initial scope and implementation order"
    return f"{prefix}-{slugify(title)}.md", title


def render_task(repo_root: Path, mode: str, intake: dict) -> tuple[str, str]:
    """Render the first task file."""
    filename, title = choose_task(repo_root, mode, intake)
    source_ref = intake.get("source_path") or "prompt-only input"
    if mode == "greenfield":
        why = "Create the first implementation scaffold from the initial project brief."
        plan = ["Set up the minimal project skeleton.", "Confirm the first user-facing workflow.", "Prepare the next implementation task."]
    elif mode == "repo-hydrate":
        why = "Align the existing repository with the new collaboration layer and identify the next concrete implementation step."
        plan = ["Review the existing code footprint.", "Map current code to project goals.", "Choose the next safe implementation increment."]
    elif low_confidence(intake):
        why = "The source plan could not be extracted reliably enough to support implementation."
        plan = ["Recover the source plan through OCR or user clarification.", "Confirm the actual project scope and goals.", "Only then schedule implementation work."]
    else:
        why = "Translate the imported project plan into a clear first implementation sequence."
        plan = ["Review the imported plan.", "Confirm the MVP scope and constraints.", "Choose the first implementation milestone."]

    body = [
        f"# {title}",
        "",
        f"{MANAGED_MARKER}",
        "",
        "## Metadata",
        "",
        f"- ID: `{filename.split('-')[0]}-{filename.split('-')[1]}`",
        "- Status: `todo`",
        "- Owner: `shared`",
        "- Created: `2026-04-22`",
        "- Updated: `2026-04-22`",
        "",
        "## Why",
        "",
        why,
        "",
        "## Scope",
        "",
        "- In scope: establish the next safe implementation step",
        "- In scope: align execution with the current project definition",
        "- Out of scope: broad speculative feature expansion",
        "",
        "## Acceptance Criteria",
        "",
        "- The next implementation step is clear.",
        "- The task aligns with the current project definition and constraints.",
        "- Open questions are explicit rather than hidden in assumptions.",
        "",
        "## Dependencies",
        "",
        f"- Files: `{source_ref}`",
        "- Decisions: `none`",
        "- External: `none`",
        "",
        "## Plan",
        "",
    ]
    body.extend([f"{index}. {step}" for index, step in enumerate(plan, start=1)])
    body.extend(
        [
            "",
            "## Notes",
            "",
            f"- Facts: initialization mode is `{mode}`",
            f"- Assumptions: intake confidence is `{intake.get('confidence')}`",
            f"- Risks: {'source plan is low-confidence' if low_confidence(intake) else 'scope still needs confirmation'}",
            "",
            "## Execution Log",
            "",
            "- `2026-04-22`: task created during repository initialization",
            "",
        ]
    )
    return filename, "\n".join(body)


def render_readme(repo_root: Path, mode: str, intake: dict, summary: dict) -> str:
    """Render README content."""
    lines = [
        f"# {summary['name']}",
        "",
        MANAGED_MARKER,
        "",
    ]
    if mode == "greenfield":
        lines.append(summary["goal"] + ".")
    elif mode == "repo-hydrate":
        lines.append("This repository was hydrated with the RepoFrame collaboration layer while preserving existing project material.")
    else:
        source_name = Path(intake.get("source_path") or "source plan").name
        lines.append(f"This repository was initialized from `{source_name}` and preserves that source as the authoritative project plan.")
    lines.extend(
        [
            "",
            "## Collaboration Contract",
            "",
            "- `AGENT.md` defines agent operating rules.",
            "- `PROJECT.md` defines the project or compatibility snapshot.",
            "- `STATUS.md` tracks the current operational state.",
            "- `DECISIONS.md` records only durable project decisions.",
            "- `tasks/` contains concrete execution work.",
        ]
    )
    if low_confidence(intake):
        lines.extend(
            [
                "",
                "## Caution",
                "",
                "The source plan could not be recovered reliably enough for implementation. This workspace is intentionally clarification-first.",
            ]
        )
    return "\n".join(lines) + "\n"


def render_agent(mode: str, intake: dict) -> str:
    """Render AGENT.md content."""
    lines = [
        "# AGENT.md",
        "",
        MANAGED_MARKER,
        "",
        "## Source Of Truth",
        "",
        "- `README.md`: human-facing repository summary",
        "- `AGENT.md`: agent operating rules",
        "- `PROJECT.md`: project definition or compatibility snapshot",
        "- `STATUS.md`: current state, blockers, and next step",
        "- `DECISIONS.md`: durable decisions only",
        "- `tasks/*.md`: execution work items",
        "",
        "## Reading Order",
        "",
        "1. `PROJECT.md`",
        "2. `STATUS.md`",
        "3. `DECISIONS.md`",
        "4. `tasks/`",
        "",
        "## Operating Rules",
        "",
        "- Preserve user-authored source plans by default.",
        "- Keep all updates consistent with the current source confidence.",
        "- Treat low-confidence intake as a clarification problem, not an implementation license.",
        "- Update `STATUS.md` when the next recommended step changes.",
        "- Add to `DECISIONS.md` only when a real durable decision exists.",
    ]
    if mode == "repo-hydrate":
        lines.extend(
            [
                "- Respect the existing repository layout and avoid reframing it as a greenfield project.",
            ]
        )
    if low_confidence(intake):
        lines.extend(
            [
                "- Do not infer product scope beyond what the source actually supports.",
            ]
        )
    lines.extend(
        [
            "",
            "## Anti-Patterns",
            "",
            "- Do not rewrite the source plan unless the user explicitly requests it.",
            "- Do not invent implementation details just to make files look complete.",
            "- Do not use ad hoc temp directories when `.repo-init/` already exists.",
            "",
        ]
    )
    return "\n".join(lines)


def render_project(repo_root: Path, mode: str, intake: dict, summary: dict) -> str:
    """Render PROJECT.md content."""
    source_path = intake.get("source_path")
    if mode == "greenfield":
        lines = [
            "# PROJECT.md",
            "",
            MANAGED_MARKER,
            "",
            "## Project Identity",
            "",
            f"- Name: `{summary['name']}`",
            f"- Type: `{summary['project_type']}`",
            f"- Stage: `{summary['stage']}`",
            "",
            "## Goal",
            "",
            summary["goal"] + ".",
            "",
            "## Constraints",
            "",
        ]
        constraints = summary["constraints"] or ["Clarify additional constraints during execution."]
        lines.extend([f"- {item}" for item in constraints])
        if summary["stack"]:
            lines.extend(["", "## Preferred Stack", ""])
            lines.extend([f"- {item}" for item in summary["stack"]])
        lines.extend(["", "## Assumptions", ""])
        lines.extend([f"- {item}" for item in summary["assumptions"]])
        return "\n".join(lines) + "\n"

    source_mode = "user-authored" if source_path else "mixed"
    lines = [
        "# Project Compatibility Layer",
        "",
        MANAGED_MARKER,
        "",
        "## Source Mode",
        "",
        f"- Source mode: `{source_mode}`",
        f"- Original source path: `{source_path or 'prompt input'}`",
        "- Rewrite policy: preserve the source plan; do not rewrite it by default",
        "",
        "## Project Snapshot",
        "",
    ]
    if low_confidence(intake):
        lines.extend(
            [
                "- Project identity: not reliably extractable from the provided source",
                "- Primary goal: not reliably extractable from the provided source",
                "- Key constraints:",
                "  - initialization must remain conservative because extraction confidence is low",
                "  - the source remains authoritative even though no usable text was extracted",
                "  - further planning should proceed only after obtaining a readable source or human clarification",
            ]
        )
    else:
        lines.append(f"- Project name: {summary['name']}")
        if summary["goal"]:
            lines.append(f"- Goal: {summary['goal']}")
        if summary["users"]:
            lines.append(f"- Target users: {summary['users']}")
        if summary["stack"]:
            lines.append(f"- Stack: {', '.join(summary['stack'])}")
        if summary["constraints"]:
            lines.append("- Key constraints:")
            lines.extend([f"  - {item}" for item in summary["constraints"]])
    lines.extend(["", "## Explicit Assumptions", ""])
    assumptions = summary["assumptions"] or ["Future work should confirm missing scope details before implementation."]
    lines.extend([f"- {item}" for item in assumptions])
    lines.extend(
        [
            "",
            "## Intake Evidence",
            "",
            f"- Detected format: `{intake.get('detected_format')}`",
            f"- Confidence: `{intake.get('confidence')}`",
            f"- Extracted word count: `{intake.get('word_count')}`",
        ]
    )
    warnings = intake.get("warnings") or []
    lines.append("- Warnings:")
    if warnings:
        lines.extend([f"  - {warning}" for warning in warnings])
    else:
        lines.append("  - none")
    return "\n".join(lines) + "\n"


def render_status(mode: str, intake: dict, summary: dict, task_filename: str) -> str:
    """Render STATUS.md content."""
    if mode == "greenfield":
        objective = f"bootstrap the initial {summary['project_type']} scaffold"
        next_step = "create the first minimal project skeleton and CLI entry point"
        state = "repository initialized from a prompt-only brief"
    elif mode == "repo-hydrate":
        objective = "align the existing repository with the collaboration workflow"
        next_step = "review the current codebase and choose the next safe implementation increment"
        state = "collaboration layer added to an existing repository"
    elif low_confidence(intake):
        objective = "clarify the source plan before any implementation work"
        next_step = "recover the plan through OCR, a better source file, or direct user clarification"
        state = "initialized from a low-confidence source plan"
    else:
        objective = "translate the imported source plan into the first implementation step"
        next_step = "confirm MVP scope and implementation order"
        state = "collaboration layer created from an imported project plan"

    blockers = "the source plan produced no usable text" if low_confidence(intake) else "none"
    risks = "any inferred scope would be speculative" if low_confidence(intake) else "scope details still need confirmation"
    lines = [
        "# STATUS.md",
        "",
        MANAGED_MARKER,
        "",
        "## Current Focus",
        "",
        f"- Active task: `{task_filename}`",
        f"- Objective: {objective}",
        "",
        "## Current State",
        "",
        "- Status: `in progress`",
        f"- Summary: {state}",
        "",
        "## Next Step",
        "",
        f"- {next_step}",
        "",
        "## Blockers",
        "",
        f"- {blockers}",
        "",
        "## Risks",
        "",
        f"- {risks}",
        "",
        "## Recently Completed",
        "",
        "- repository initialization and collaboration-file setup",
        "",
        "## Last Updated",
        "",
        "- Date: `2026-04-22`",
        "- By: `agent`",
        "",
    ]
    return "\n".join(lines)


def render_decisions() -> str:
    """Render DECISIONS.md content."""
    return "\n".join(
        [
            "# DECISIONS.md",
            "",
            MANAGED_MARKER,
            "",
            "No durable project decisions were established during initialization.",
            "",
        ]
    )


def write_managed_file(path: Path, content: str) -> None:
    """Write a managed file."""
    path.write_text(content, encoding="utf-8")


def append_if_missing(path: Path, section_title: str, section_body: str) -> None:
    """Append a section to a populated file if it is not already present."""
    existing = path.read_text(encoding="utf-8", errors="replace")
    if section_title in existing:
        return
    updated = existing.rstrip() + "\n\n" + section_body.strip() + "\n"
    path.write_text(updated, encoding="utf-8")


def apply_outputs(repo_root: Path, intake: dict, mode: str, policy_json: dict) -> dict[str, list[str]]:
    """Write repository outputs according to the computed policy."""
    summary = infer_greenfield_fields(intake, repo_root) if mode == "greenfield" else infer_plan_snapshot(intake, repo_root)
    filename, task_content = render_task(repo_root, mode, intake)
    task_path = repo_root / "tasks" / filename
    tasks_dir_preexisted = task_path.parent.exists()
    task_preexisted = task_path.exists()
    task_path.parent.mkdir(parents=True, exist_ok=True)
    task_path.write_text(task_content, encoding="utf-8")

    readme_text = render_readme(repo_root, mode, intake, summary)
    agent_text = render_agent(mode, intake)
    project_text = render_project(repo_root, mode, intake, summary)
    status_text = render_status(mode, intake, summary, filename)
    decisions_text = render_decisions()

    created: list[str] = []
    supplemented: list[str] = []
    preserved: list[str] = []

    content_map = {
        "README.md": readme_text,
        "AGENT.md": agent_text,
        "PROJECT.md": project_text,
        "STATUS.md": status_text,
        "DECISIONS.md": decisions_text,
    }

    for target in TARGET_FILES:
        path = repo_root / target
        policy = policy_json["files"][target]["policy"]
        state = policy_json["files"][target]["state"]

        if target == "PROJECT.md" and policy == "preserve":
            preserved.append(target)
            continue

        if policy == "create" or state in {"missing", "empty", "template"}:
            write_managed_file(path, content_map[target])
            created.append(target)
            continue

        if target == "README.md":
            append_if_missing(
                path,
                "## Collaboration Layer",
                "\n".join(
                    [
                        "## Collaboration Layer",
                        "",
                        "This repository now uses the RepoFrame collaboration files:",
                        "",
                        "- `AGENT.md`",
                        "- `PROJECT.md`",
                        "- `STATUS.md`",
                        "- `DECISIONS.md`",
                        "- `tasks/`",
                    ]
                ),
            )
            supplemented.append(target)
            continue

        if path.exists() and MANAGED_MARKER in path.read_text(encoding="utf-8", errors="replace"):
            write_managed_file(path, content_map[target])
            supplemented.append(target)
            continue

        preserved.append(target)

    if not tasks_dir_preexisted or not task_preexisted:
        created.append("tasks/")
    else:
        supplemented.append("tasks/")

    return {
        "created": unique(created),
        "supplemented": unique(supplemented),
        "preserved": unique(preserved),
    }


def main() -> int:
    """Run end-to-end repository initialization."""
    args = parse_args()
    try:
        repo_root = Path(args.repo).resolve()
        repo_root.mkdir(parents=True, exist_ok=True)
        artifacts_dir = select_artifacts_dir(repo_root, args.artifacts_dir)
        artifacts_dir.mkdir(parents=True, exist_ok=True)

        raw, intake = collect_source_inputs(args, repo_root, artifacts_dir)
        write_json(raw, str(artifacts_dir / "raw-intake.json"))
        write_json(intake, str(artifacts_dir / "intake.json"))

        repo_summary = summarize_repo(repo_root)
        mode, reasons = choose_mode(intake, repo_summary)
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

        file_changes = apply_outputs(repo_root, intake, mode, policy_json)
        report_path = Path(args.report_path).resolve() if args.report_path else artifacts_dir / "init-report.md"
        assumptions = []
        if low_confidence(intake):
            assumptions.append("Initialization was kept conservative because the source confidence is low.")
        report_text = render_markdown(intake, mode_json, policy_json, assumptions, [])
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(report_text, encoding="utf-8")

        result = {
            "mode": mode,
            "repo": str(repo_root),
            "artifacts_dir": str(artifacts_dir),
            "report_path": str(report_path),
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
