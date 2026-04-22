#!/usr/bin/env python3
"""Run the deterministic end-to-end repo initialization flow."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from pathlib import Path

from build_source_bundle import build_source_bundle
from classify_init_mode import choose_mode
from plan_write_policy import build_write_policy
from render_init_report import render_markdown
from repo_init_common import (
    DEFAULT_ARTIFACT_DIRNAME,
    MANAGED_MARKER,
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


def find_labeled_value(text: str, labels: list[str]) -> str:
    """Find a single-line labeled value."""
    patterns = [re.escape(label) for label in labels]
    match = re.search(rf"(?:{'|'.join(patterns)})\s*[:：]\s*(.+?)(?:$|\n)", text, re.IGNORECASE)
    return normalize_text(match.group(1)) if match else ""


def split_stack_items(text: str) -> list[str]:
    """Split a stack sentence or section into items."""
    raw = text.replace("\n", ", ")
    raw = raw.replace(" and ", ", ")
    items = [item.strip(" -") for item in raw.split(",")]
    return unique([item for item in items if item])


def infer_project_name(title: str, text: str, repo_root: Path) -> str:
    """Infer a project name."""
    patterns = [
        r"\bcalled\s+([A-Z][A-Za-z0-9_-]+)",
        r"\bnamed\s+([A-Z][A-Za-z0-9_-]+)",
        r"^\s*project\s*[:：]\s*([A-Za-z0-9 _-]+)$",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
        if match:
            return normalize_text(match.group(1))
    if title and title.lower() not in {"prompt input", "project-plan", "untitled project input"}:
        cleaned = re.sub(r"\b(html|docx|pdf)\b.*$", "", title, flags=re.IGNORECASE).strip(" -")
        if cleaned:
            return cleaned
    return repo_root.name or "Project"


def infer_greenfield_fields(intake: dict, repo_root: Path) -> dict:
    """Infer structured fields from prompt input."""
    text = intake.get("extracted_text", "")
    name = infer_project_name(intake.get("title") or "", text, repo_root)
    goal = find_labeled_value(text, ["goal", "objective", "purpose"])
    project_type_match = re.search(r"initialize this repository as (?:an?|the)\s+(.+?)(?:\s+called|\s+named|\.|,|\n)", text, re.IGNORECASE)
    project_type = project_type_match.group(1).strip() if project_type_match else "project"
    stage = find_labeled_value(text, ["stage"]).lower()
    stack_match = re.search(r"\buse\s+(.+?)(?:[.\n]|$)", text, re.IGNORECASE)
    stack = split_stack_items(stack_match.group(1)) if stack_match else []
    constraints = []
    if stack:
        constraints.append("Use " + ", ".join(stack) + ".")
    constraints.extend([line.strip() for line in text.splitlines() if line.lower().startswith("do not ")])
    return {
        "name": name,
        "project_type": project_type,
        "stage": stage or "prototype",
        "goal": goal or "Clarify the primary project outcome.",
        "users": find_labeled_value(text, ["users", "target users", "audience"]),
        "stack": stack,
        "constraints": unique(constraints),
        "assumptions": [
            "The repository starts empty enough for the collaboration layer to define the initial working structure.",
            "The brief is sufficient to start implementation planning without a separate full product specification.",
        ],
    }


def infer_plan_snapshot(intake: dict, repo_root: Path) -> dict:
    """Infer a safe project snapshot from plan-ingest input."""
    text = intake.get("extracted_text", "")
    goal = find_section(text, ["goal", "primary goal"]) or find_labeled_value(text, ["goal", "objective", "purpose"])
    users = find_section(text, ["users", "target users"]) or find_labeled_value(text, ["users", "target users", "audience"])
    stack = find_section(text, ["stack", "tech stack", "technology stack"]) or find_labeled_value(
        text,
        ["stack", "tech stack", "technology stack"],
    )
    constraints = find_section(text, ["constraints"]) or find_labeled_value(text, ["constraints"])
    return {
        "name": infer_project_name(intake.get("title") or "", text, repo_root),
        "project_type": find_labeled_value(text, ["type", "project type"]),
        "stage": find_labeled_value(text, ["stage"]).lower(),
        "goal": goal.rstrip("."),
        "users": users.rstrip("."),
        "stack": split_stack_items(stack) if stack else [],
        "constraints": unique([line.strip("- ") for line in constraints.splitlines() if line.strip()]) if constraints else [],
        "assumptions": [
            "The provided source document remains the authoritative project definition unless the user asks for a rewrite.",
        ],
    }


def merged_summary(intake: dict, repo_root: Path, mode: str) -> dict:
    """Build a project summary from bundle intake with backwards-compatible fallbacks."""
    base = {
        "name": repo_root.name or "Project",
        "project_type": "project",
        "stage": "",
        "goal": "",
        "users": "",
        "stack": [],
        "constraints": [],
        "assumptions": [],
    }
    merged = intake.get("merged_snapshot") or {}
    for key in base:
        value = merged.get(key)
        if value not in (None, "", []):
            base[key] = value

    fallback = infer_greenfield_fields(intake, repo_root) if mode == "greenfield" else infer_plan_snapshot(intake, repo_root)
    for key in base:
        if base[key] in (None, "", []):
            base[key] = fallback.get(key, base[key])

    base["assumptions"] = unique([*(fallback.get("assumptions") or []), *(merged.get("assumptions") or []), *(base.get("assumptions") or [])])
    return base


def low_confidence(intake: dict) -> bool:
    """Return True when intake should be handled conservatively."""
    confidence = intake.get("bundle_confidence", intake.get("confidence", 0))
    return confidence < 0.5 or not intake.get("extracted_text", "").strip()


def needs_clarification(intake: dict) -> bool:
    """Return True when unresolved questions remain."""
    return low_confidence(intake) or bool(intake.get("clarification_questions"))


def repo_state_snapshot(repo_root: Path) -> dict[str, str | list[str]]:
    """Infer coarse repository identity from existing docs."""
    texts: list[str] = []
    for name in ("PROJECT.md", "README.md"):
        path = repo_root / name
        if path.exists():
            texts.append(path.read_text(encoding="utf-8", errors="replace"))
    text = normalize_text("\n\n".join(texts))
    if not text:
        return {}
    title = text.splitlines()[0].lstrip("# ").strip() if text.splitlines() else repo_root.name
    stack = find_section(text, ["preferred stack", "stack", "tech stack"]) or find_labeled_value(text, ["stack", "tech stack"])
    return {
        "name": infer_project_name(title, text, repo_root),
        "goal": find_section(text, ["goal"]) or find_labeled_value(text, ["goal", "objective"]),
        "stack": split_stack_items(stack) if stack else [],
    }


def canonical_field_value(value: str | list[str]) -> str:
    """Canonicalize values for comparison."""
    if isinstance(value, list):
        return " | ".join(sorted(unique([normalize_text(item).lower() for item in value if normalize_text(item)])))
    return normalize_text(str(value or "")).lower()


def detect_repo_hydrate_clarifications(repo_root: Path, intake: dict) -> tuple[list[str], list[str]]:
    """Detect repo-hydrate conflicts between bundle input and existing repository docs."""
    existing = repo_state_snapshot(repo_root)
    if not existing:
        return [], []

    merged = intake.get("merged_snapshot") or {}
    questions: list[str] = []
    warnings: list[str] = []
    for field in ("name", "goal", "stack"):
        existing_value = existing.get(field)
        merged_value = merged.get(field)
        if canonical_field_value(existing_value) and canonical_field_value(merged_value):
            if canonical_field_value(existing_value) != canonical_field_value(merged_value):
                questions.append(
                    f"The existing repository suggests `{field}` is `{existing_value}`, but the source bundle suggests `{merged_value}`. Confirm which should drive hydration."
                )
                warnings.append(f"Existing repository state and source bundle differ on `{field}`.")
    return unique(questions), unique(warnings)


def source_reference(intake: dict) -> str:
    """Return a readable source reference."""
    roles = intake.get("source_roles") or []
    if roles:
        return ", ".join(item["label"] for item in roles)
    return intake.get("source_path") or "prompt-only input"


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
    elif needs_clarification(intake):
        title = "Clarify source bundle and recover missing scope"
    else:
        title = "Clarify initial scope and implementation order"
    return f"{prefix}-{slugify(title)}.md", title


def render_task(repo_root: Path, mode: str, intake: dict) -> tuple[str, str]:
    """Render the first task file."""
    filename, title = choose_task(repo_root, mode, intake)
    source_ref = source_reference(intake)
    questions = intake.get("clarification_questions") or []

    if mode == "greenfield":
        why = "Create the first implementation scaffold from the initial project brief."
        plan = ["Set up the minimal project skeleton.", "Confirm the first user-facing workflow.", "Prepare the next implementation task."]
    elif mode == "repo-hydrate":
        why = "Align the existing repository with the new collaboration layer and identify the next concrete implementation step."
        plan = ["Review the existing code footprint.", "Map current code to project goals.", "Choose the next safe implementation increment."]
    elif needs_clarification(intake):
        why = "The source bundle still contains unresolved questions or low-confidence extraction."
        plan = ["Review the source bundle and conflicts.", "Confirm unresolved project facts with the user.", "Only then schedule implementation work."]
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
            f"- Facts: source count is `{intake.get('source_count', 0)}`",
            f"- Assumptions: intake confidence is `{intake.get('bundle_confidence', intake.get('confidence'))}`",
            f"- Risks: {'unresolved conflicts or low-confidence extraction remain' if needs_clarification(intake) else 'scope still needs confirmation'}",
        ]
    )
    if questions:
        body.extend(["- Open questions:"] + [f"  - {question}" for question in questions[:5]])
    body.extend(
        [
            "",
            "## Execution Log",
            "",
            "Record milestone-level progress here. Each entry should summarize one meaningful execution batch, task-status transition, blocker change, or user-directed change of course.",
            "",
            "Do not log every file save, every tiny edit, or every formatting-only change.",
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
        if intake.get("source_count", 0) > 1:
            lines.append(
                f"This repository was initialized from `{intake.get('source_count')}` source files. The default primary source is `{Path(intake.get('primary_source') or 'source').name}`."
            )
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
    if needs_clarification(intake):
        lines.extend(
            [
                "",
                "## Caution",
                "",
                "This workspace is currently clarification-first because the source bundle contains unresolved questions or low-confidence extraction.",
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
        "- Update the current task file when task status, execution direction, or blocker state materially changes.",
        "- Append to the task `Execution Log` only after a meaningful execution batch or milestone.",
        "- Add to `DECISIONS.md` only when a real durable decision exists.",
    ]
    if mode == "repo-hydrate":
        lines.append("- Respect the existing repository layout and avoid reframing it as a greenfield project.")
    if needs_clarification(intake):
        lines.append("- Do not infer product scope beyond what the source bundle actually supports.")
    lines.extend(
        [
            "",
            "## Update Rules",
            "",
            "Update `STATUS.md` when:",
            "",
            "- the active task changes",
            "- progress reaches a milestone",
            "- a blocker appears or is removed",
            "- the next recommended step changes",
            "",
            "Update a task file when:",
            "",
            "- the task is created",
            "- acceptance criteria change",
            "- implementation notes materially affect execution",
            "- the task status changes",
            "- a blocker appears or is removed",
            "- a meaningful batch of related repository changes completes",
            "",
            "Update the task `Execution Log` when:",
            "",
            "- a milestone is reached",
            "- a task status changes",
            "- a blocker appears or is removed",
            "- a meaningful batch of related repository changes completes",
            "- a user decision materially changes the execution path",
            "",
            "Do not update the task `Execution Log` for:",
            "",
            "- every file save",
            "- every small refactor or formatting-only edit",
            "- every micro-step inside the same execution batch",
            "- changes that are already obvious from git history and do not affect execution understanding",
            "",
            "## Anti-Patterns",
            "",
            "- Do not rewrite the source plan unless the user explicitly requests it.",
            "- Do not invent implementation details just to make files look complete.",
            "- Do not use ad hoc temp directories when `.repo-init/` already exists.",
            "- Do not turn the task `Execution Log` into a file-by-file or save-by-save change ledger.",
            "",
        ]
    )
    return "\n".join(lines)


def render_project(repo_root: Path, mode: str, intake: dict, summary: dict) -> str:
    """Render PROJECT.md content."""
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
            lines.extend(["", "## Preferred Stack", ""] + [f"- {item}" for item in summary["stack"]])
        lines.extend(["", "## Assumptions", ""] + [f"- {item}" for item in summary["assumptions"]])
        return "\n".join(lines) + "\n"

    source_roles = intake.get("source_roles") or []
    field_sources = intake.get("field_sources") or {}
    conflicts = intake.get("conflicts") or []
    questions = intake.get("clarification_questions") or []
    lines = [
        "# Project Compatibility Layer",
        "",
        MANAGED_MARKER,
        "",
        "## Source Mode",
        "",
        f"- Source mode: `{'user-authored' if intake.get('source_path') else 'mixed'}`",
        f"- Primary source: `{intake.get('primary_source') or intake.get('source_path') or 'prompt input'}`",
        f"- Source count: `{intake.get('source_count', 0)}`",
        "- Rewrite policy: preserve the source plan; do not rewrite it by default",
        "",
        "## Source Bundle",
        "",
    ]
    if source_roles:
        lines.extend([f"- `{item['label']}`: role=`{item['role']}`, confidence=`{item['confidence']}`" for item in source_roles])
    else:
        lines.append("- prompt-only input")

    lines.extend(["", "## Project Snapshot", ""])
    snapshot_lines = [
        ("Project name", "name", summary["name"]),
        ("Goal", "goal", summary["goal"]),
        ("Target users", "users", summary["users"]),
        ("Stage", "stage", summary["stage"]),
        ("Type", "project_type", summary["project_type"]),
    ]
    for label, field_name, value in snapshot_lines:
        if value:
            source_label = field_sources.get(field_name, "")
            source_note = f" (from `{source_label}`)" if source_label else ""
            lines.append(f"- {label}: {value}{source_note}")
    if summary["stack"]:
        stack_note = f" (from `{field_sources['stack']}`)" if field_sources.get("stack") else ""
        lines.append(f"- Stack: {', '.join(summary['stack'])}{stack_note}")
    if summary["constraints"]:
        lines.append("- Key constraints:")
        lines.extend([f"  - {item}" for item in summary["constraints"]])

    lines.extend(["", "## Explicit Assumptions", ""])
    assumptions = unique([*(summary.get("assumptions") or []), *intake.get("adopted_defaults", [])])
    if assumptions:
        lines.extend([f"- {item}" for item in assumptions])
    else:
        lines.append("- none")

    lines.extend(
        [
            "",
            "## Intake Evidence",
            "",
            f"- Detected format: `{intake.get('detected_format')}`",
            f"- Bundle confidence: `{intake.get('bundle_confidence', intake.get('confidence'))}`",
            f"- Extracted word count: `{intake.get('word_count')}`",
        ]
    )
    warnings = intake.get("warnings") or []
    lines.append("- Warnings:")
    if warnings:
        lines.extend([f"  - {warning}" for warning in warnings])
    else:
        lines.append("  - none")

    lines.extend(["", "## Conflicts", ""])
    if conflicts:
        lines.extend([f"- `{item['field']}`: chose `{item['chosen_from']}` over `{item['discarded_from']}`" for item in conflicts])
    else:
        lines.append("- none")

    lines.extend(["", "## Open Questions", ""])
    if questions:
        lines.extend([f"- {question}" for question in questions])
    else:
        lines.append("- none")
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
    elif needs_clarification(intake):
        objective = "clarify the source bundle before any implementation work"
        next_step = "resolve the current open questions or confirm the default authority ordering"
        state = "initialized from a source bundle that still needs clarification"
    else:
        objective = "translate the imported source plan into the first implementation step"
        next_step = "confirm MVP scope and implementation order"
        state = "collaboration layer created from an imported project plan"

    blockers = "unresolved source-bundle questions remain" if needs_clarification(intake) else "none"
    risks = "any inferred scope may still be speculative" if needs_clarification(intake) else "scope details still need confirmation"
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
        f"- Status: `{'blocked' if needs_clarification(intake) else 'in progress'}`",
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
    summary = merged_summary(intake, repo_root, mode)
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

        write_json(raw_bundle, str(artifacts_dir / "raw-intake.json"))
        write_json(intake, str(artifacts_dir / "intake.json"))

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
