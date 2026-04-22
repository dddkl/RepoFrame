#!/usr/bin/env python3
"""Markdown rendering helpers for repo initialization."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from init_summary import needs_clarification
from init_task_plan import TaskPlan
from repo_init_common import MANAGED_MARKER, unique


def _ensure_sentence(text: str, fallback: str) -> str:
    """Return a non-empty sentence with terminal punctuation."""
    value = (text or "").strip() or fallback
    if value[-1] not in ".!?":
        value += "."
    return value


def _source_label(value: str | None) -> str:
    """Return a readable source label for README output."""
    if not value:
        return "prompt-only input"
    return Path(value).name or value


def _source_files_used(intake: dict[str, Any]) -> str:
    """Return a readable source-file summary for README output."""
    source_roles = intake.get("source_roles") or []
    items = [
        f"`{_source_label(item.get('path') or item.get('label'))}`"
        for item in source_roles
        if item.get("path") or item.get("label")
    ]
    return ", ".join(items) if items else "`prompt-only input`"


def _readme_overview(mode: str, intake: dict[str, Any], summary: dict[str, Any]) -> str:
    """Render the opening README paragraph."""
    if mode == "greenfield":
        return _ensure_sentence(summary.get("goal", ""), "Clarify the primary project outcome.")
    if mode == "repo-hydrate":
        return "This repository was hydrated with the RepoFrame collaboration layer while preserving existing project material."
    if intake.get("source_count", 0) > 1:
        return (
            f"This repository was initialized from `{intake.get('source_count')}` source files. "
            f"The default primary source is `{_source_label(intake.get('primary_source'))}`."
        )
    return (
        f"This repository was initialized from `{_source_label(intake.get('source_path'))}` "
        "and preserves that source as the authoritative project plan."
    )


def _repository_purpose(mode: str, summary: dict[str, Any]) -> str:
    """Render the repository-purpose section."""
    if mode == "greenfield":
        return _ensure_sentence(summary.get("goal", ""), "Clarify the primary project outcome.")
    if mode == "repo-hydrate":
        goal = _ensure_sentence(
            summary.get("goal", ""),
            "Keep the existing repository legible to both humans and agents as work continues",
        )
        return goal + " RepoFrame adds explicit project context, status tracking, durable decisions, and task sequencing around the existing codebase."
    goal = _ensure_sentence(
        summary.get("goal", ""),
        "Turn the imported project plan into a collaboration workspace that stays readable during execution",
    )
    return goal + " RepoFrame preserves the source plan while making execution state, decisions, and task sequencing explicit."


def _initialization_model_lines(mode: str, intake: dict[str, Any]) -> list[str]:
    """Render initialization-model bullets for README output."""
    lines = [
        f"- Mode: `{mode}`",
        "- Posture: `preserve-first` by default",
        f"- Primary source: `{_source_label(intake.get('primary_source') or intake.get('source_path'))}`",
        f"- Source files used: {_source_files_used(intake)}",
    ]
    if needs_clarification(intake):
        lines.append("- Current confidence: clarification-first until unresolved questions are answered")
    else:
        lines.append("- Current confidence: sufficient to create the collaboration layer and starting task set")
    return lines


def _build_readme_contract_sections(mode: str, intake: dict[str, Any], summary: dict[str, Any], heading: str) -> list[str]:
    """Render the README contract sections with a configurable heading level."""
    lines = [
        f"{heading} Repository Purpose",
        "",
        _repository_purpose(mode, summary),
        "",
        f"{heading} Initialization Model",
        "",
        *_initialization_model_lines(mode, intake),
        "",
        f"{heading} Collaboration Contract",
        "",
        "- `AGENT.md` defines agent operating rules and update discipline.",
        "- `PROJECT.md` defines the project or compatibility snapshot.",
        "- `STATUS.md` tracks current state, latest feedback, task impact, and replan suggestions.",
        "- `DECISIONS.md` records only durable project decisions.",
        "- `tasks/` contains concrete execution work, assumption checks, and downstream impact.",
        "",
        f"{heading} Detailed Rules",
        "",
        "- `AGENT.md` is the operational source of truth for execution and update rules.",
        "- `PROJECT.md` explains project scope, constraints, and compatibility assumptions.",
        "- `STATUS.md` and `tasks/` show the active work surface and next recommended step.",
        "- `.repo-init/init-report.md` records initialization evidence, source handling, and planned file actions.",
    ]
    task_decomposition = intake.get("task_decomposition") or {}
    if task_decomposition.get("applied"):
        lines.extend(
            [
                "",
                f"{heading} Task Decomposition",
                "",
                "This workspace was classified as complex during initialization, so RepoFrame generated a coordinating master task and first-wave child tasks.",
                f"The recommended starting child task is `{task_decomposition.get('recommended_start_task')}`.",
            ]
        )
    if needs_clarification(intake):
        lines.extend(
            [
                "",
                f"{heading} Caution",
                "",
                "This workspace is currently clarification-first because the source bundle contains unresolved questions or low-confidence extraction.",
            ]
        )
    return lines


def render_readme(repo_root: Path, mode: str, intake: dict[str, Any], summary: dict[str, Any]) -> str:
    """Render README content."""
    lines = [
        f"# {summary['name']}",
        "",
        MANAGED_MARKER,
        "",
        _readme_overview(mode, intake, summary),
        "",
    ]
    lines.extend(_build_readme_contract_sections(mode, intake, summary, "##"))
    return "\n".join(lines) + "\n"


def render_readme_supplement(mode: str, intake: dict[str, Any], summary: dict[str, Any]) -> str:
    """Render the README supplement for populated non-managed README files."""
    lines = [
        "## Collaboration Layer",
        "",
        "RepoFrame added a collaboration layer to this repository so project context, current state, decisions, and task sequencing stay visible without replacing the existing README.",
        "",
        *_build_readme_contract_sections(mode, intake, summary, "###"),
    ]
    return "\n".join(lines) + "\n"


def render_agent(mode: str, intake: dict[str, Any]) -> str:
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
        "- `STATUS.md`: current state, latest feedback, task impact, replan suggestions, blockers, and next step",
        "- `DECISIONS.md`: durable accepted decisions only",
        "- `tasks/*.md`: execution work items",
        "",
        "## Reading Order",
        "",
        "1. `PROJECT.md`",
        "2. `STATUS.md`",
        "3. `DECISIONS.md`",
        "4. the coordinating task in `tasks/` when one exists",
        "5. the relevant child task in `tasks/`",
        "",
        "## Operating Rules",
        "",
        "- Preserve user-authored source plans by default.",
        "- Keep all updates consistent with the current source confidence.",
        "- Treat low-confidence intake as a clarification problem, not an implementation license.",
        "- Treat initialization as complete once the collaboration files, first task, and initialization report exist.",
        "- Do not begin implementation after initialization unless the user explicitly asks for post-init execution.",
        "- When a coordinating master task exists, use it to sequence child tasks and keep `STATUS.md` pointed at the master task until a child task is explicitly chosen.",
        "- When a task reaches a milestone, blocker change, acceptance change, assumption invalidation, or user-directed change, update that task's `Assumption Checks` and `Downstream Impact` before closing the execution batch.",
        "- When task-local feedback affects unfinished work, update the coordinating master task `Feedback Ledger` plus `STATUS.md` `Latest Feedback`, `Task Impact`, and `Recommended Replan`.",
        "- For single-task work, let `STATUS.md` carry the current feedback and replan suggestion without inventing a coordinating task.",
        "- Treat `Recommended Replan` as suggestion space until downstream changes are explicitly accepted.",
        "- Do not rewrite untouched task status or acceptance criteria from a single unconfirmed feedback cycle.",
        "- Append to the task `Execution Log` only after a meaningful execution batch or milestone.",
        "- Add to `DECISIONS.md` only when a real durable decision or explicitly accepted replan outcome exists.",
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
            "- latest feedback changes",
            "- task impact or recommended replan changes",
            "- a blocker appears or is removed",
            "- the next recommended step changes",
            "",
            "Update `DECISIONS.md` when:",
            "",
            "- a non-trivial technical choice is accepted",
            "- a replan decision is explicitly accepted and should become durable",
            "- an option is rejected for a concrete reason",
            "- a previous decision is reversed",
            "",
            "Update a task file when:",
            "",
            "- the task is created",
            "- acceptance criteria change",
            "- assumption validation state changes",
            "- downstream impact changes",
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
            "- a downstream impact or replan recommendation becomes material to future tasks",
            "",
            "If an `Execution Log` entry changes downstream work, also update `Downstream Impact`; do not leave that impact only in the log.",
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
            "- Do not store temporary feedback notes or unaccepted replan suggestions in `DECISIONS.md`.",
            "- Do not rewrite not-yet-started task status or acceptance criteria from a single unconfirmed feedback cycle.",
            "",
        ]
    )
    return "\n".join(lines)


def render_project(repo_root: Path, mode: str, intake: dict[str, Any], summary: dict[str, Any]) -> str:
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


def render_status(mode: str, intake: dict[str, Any], summary: dict[str, Any], task_plan: TaskPlan) -> str:
    """Render STATUS.md content."""
    task_decomposition = intake.get("task_decomposition") or {}
    active_task = task_plan["active_task"]
    latest_feedback = [
        "No execution feedback recorded yet. Add 1-3 high-signal conclusions after the next meaningful execution batch."
    ]
    task_impact = [
        "No downstream task impact recorded yet. Record affected tasks as `keep | reorder | block | split | revise-acceptance | clarify` when feedback changes future work."
    ]
    if task_decomposition.get("applied"):
        recommended_replan = [
            f"Suggested only: confirm `{task_plan['recommended_start_task']}` as the first child task before changing the generated order.",
            "Keep the current child-task order until execution feedback or accepted replan decisions justify a change.",
        ]
    elif needs_clarification(intake):
        recommended_replan = [
            "Suggested only: resolve the current clarification questions before reprioritizing or starting implementation work."
        ]
    else:
        recommended_replan = [
            "Suggested only: keep the current task sequence until fresh execution feedback justifies a change."
        ]

    if task_decomposition.get("applied"):
        if mode == "greenfield":
            objective = "coordinate the decomposed greenfield delivery plan"
        elif mode == "repo-hydrate":
            objective = "coordinate the decomposed repository hydration plan"
        else:
            objective = "coordinate the decomposed imported-plan execution"
        next_step = f"review `{task_plan['recommended_start_task']}` and explicitly confirm it as the first execution slice"
        state = "complex task decomposition created during initialization; awaiting explicit execution"
        status_value = "not started"
        blockers = "none"
        risks = "task order may still need reprioritization once explicit execution begins"
        recently_completed = (
            f"- initialization created coordinating task `{task_plan['master_task']}` and `{len(task_plan['child_tasks'])}` child tasks"
        )
    elif mode == "greenfield":
        objective = f"bootstrap the initial {summary['project_type']} scaffold"
        next_step = "create the first minimal project skeleton and CLI entry point"
        state = "repository initialized from a prompt-only brief"
        status_value = "in progress"
        blockers = "none"
        risks = "scope details still need confirmation"
        recently_completed = "- repository initialization and collaboration-file setup"
    elif mode == "repo-hydrate":
        objective = "align the existing repository with the collaboration workflow"
        next_step = "review the current codebase and choose the next safe implementation increment"
        state = "collaboration layer added to an existing repository"
        status_value = "in progress"
        blockers = "none"
        risks = "scope details still need confirmation"
        recently_completed = "- repository initialization and collaboration-file setup"
    elif needs_clarification(intake):
        objective = "clarify the source bundle before any implementation work"
        next_step = "resolve the current open questions or confirm the default authority ordering"
        state = "initialized from a source bundle that still needs clarification"
        status_value = "blocked"
        blockers = "unresolved source-bundle questions remain"
        risks = "any inferred scope may still be speculative"
        recently_completed = "- repository initialization and collaboration-file setup"
    else:
        objective = "translate the imported source plan into the first implementation step"
        next_step = "confirm MVP scope and implementation order"
        state = "collaboration layer created from an imported project plan"
        status_value = "in progress"
        blockers = "none"
        risks = "scope details still need confirmation"
        recently_completed = "- repository initialization and collaboration-file setup"

    lines = [
        "# STATUS.md",
        "",
        MANAGED_MARKER,
        "",
        "## Current Focus",
        "",
        f"- Active task: `{active_task}`",
        f"- Objective: {objective}",
        "",
        "## Current State",
        "",
        f"- Status: `{status_value}`",
        f"- Summary: {state}",
        "",
        "## Latest Feedback",
        "",
    ]
    lines.extend([f"- {item}" for item in latest_feedback])
    lines.extend(
        [
            "",
            "## Task Impact",
            "",
        ]
    )
    lines.extend([f"- {item}" for item in task_impact])
    lines.extend(
        [
            "",
            "## Recommended Replan",
            "",
        ]
    )
    lines.extend([f"- {item}" for item in recommended_replan])
    lines.extend(
        [
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
            recently_completed,
            "",
            "## Last Updated",
            "",
            "- Date: `2026-04-22`",
            "- By: `agent`",
            "",
        ]
    )
    return "\n".join(lines)


def render_decisions() -> str:
    """Render DECISIONS.md content."""
    return "\n".join(
        [
            "# DECISIONS.md",
            "",
            MANAGED_MARKER,
            "",
            "This file stores durable, accepted project decisions only.",
            "",
            "Keep temporary feedback notes and unaccepted replan suggestions in `STATUS.md` or the coordinating task instead of here.",
            "",
            "No durable project decisions were established during initialization.",
            "",
        ]
    )
