#!/usr/bin/env python3
"""Markdown rendering helpers for repo initialization."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from init_summary import needs_clarification
from init_task_plan import TaskPlan, goal_id_from_filename
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
        lines.append("- Current confidence: sufficient to create the collaboration layer, active goal, and planned tasks")
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
        "- `AGENT.md` is a thin operating index for agents.",
        "- `.agent/` contains detailed collaboration rules that agents read only when relevant.",
        "- `PROJECT.md` defines the project or compatibility snapshot.",
        "- `goals/` contains milestone goals, observations, planned tasks, and replan history.",
        "- `acceptance.json` contains machine-checkable milestone acceptance criteria.",
        "- `STATUS.md` tracks current focus, latest feedback, task impact, and replan suggestions.",
        "- `DECISIONS.md` records only durable project decisions.",
        "- `tasks/` contains provisional execution plans, assumption checks, and downstream impact.",
        "",
        f"{heading} Detailed Rules",
        "",
        "- `AGENT.md` routes agents to the right detailed rule file.",
        "- `.agent/replanning.md` defines when agents may rewrite tasks while preserving the goal.",
        "- `.agent/collaboration-rule-changes.md` defines how collaboration-contract changes are accepted.",
        "- `PROJECT.md` explains project scope, constraints, and compatibility assumptions.",
        "- `STATUS.md`, `goals/`, and `tasks/` show the active work surface and next recommended step.",
        "- `.repo-init/init-report.md` records initialization evidence, source handling, and planned file actions.",
    ]
    planning = intake.get("adaptive_task_planning") or {}
    if planning.get("multi_task"):
        lines.extend(
            [
                "",
                f"{heading} Adaptive Task Planning",
                "",
                "This workspace was classified as complex during initialization, so RepoFrame generated milestone goals plus multiple planned tasks.",
                f"The recommended starting task is `{planning.get('recommended_start_task')}`.",
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
    """Render thin AGENT.md content."""
    lines = [
        "# AGENT.md",
        "",
        MANAGED_MARKER,
        "",
        "This file is the thin operating index for agents working in this repository.",
        "",
        "## Source Of Truth",
        "",
        "- `README.md`: human-facing repository summary",
        "- `AGENT.md`: agent entry point and rule index",
        "- `.agent/*.md`: detailed collaboration rules",
        "- `PROJECT.md`: project definition or compatibility snapshot",
        "- `goals/*.md`: active goals, observations, planned tasks, and replan history",
        "- `STATUS.md`: current focus, latest feedback, task impact, replan suggestions, blockers, and next step",
        "- `DECISIONS.md`: durable accepted decisions only",
        "- `tasks/*.md`: provisional execution plans and task-local records",
        "",
        "## Reading Order",
        "",
        "1. `PROJECT.md`",
        "2. `STATUS.md`",
        "3. `DECISIONS.md`",
        "4. the active milestone goal in `goals/`",
        "5. `acceptance.json`",
        "6. the active task in `tasks/` when one is active",
        "",
        "## Read Detailed Rules When Needed",
        "",
        "- Read `.agent/operating-rules.md` before substantial implementation work.",
        "- Read `.agent/replanning.md` before rewriting, splitting, superseding, or reordering tasks.",
        "- Read `.agent/file-contract.md` before changing collaboration files or generated file structure.",
        "- Read `.agent/collaboration-rule-changes.md` before changing the collaboration contract itself.",
        "",
        "## Core Invariants",
        "",
        "- Preserve user-authored source plans by default.",
        "- Treat low-confidence intake as a clarification problem, not an implementation license.",
        "- Initialization creates the collaboration layer, milestone goals, planned tasks, `acceptance.json`, and report; it does not authorize implementation in the same turn.",
        "- Use tasks as provisional plans toward the active milestone goal; rewrite them when observations show a better route.",
        "- Do not change the goal, hard constraints, durable project scope, accepted success criteria, or collaboration contract without explicit human confirmation.",
        "- Record durable accepted decisions in `DECISIONS.md`; keep temporary feedback and unaccepted rule-change proposals out of it.",
    ]
    if mode == "repo-hydrate":
        lines.append("- Respect the existing repository layout and avoid reframing it as a greenfield project.")
    if needs_clarification(intake):
        lines.append("- Do not infer product scope beyond what the source bundle actually supports.")
    lines.append("")
    return "\n".join(lines)


def render_agent_docs() -> dict[str, str]:
    """Render detailed generated agent-rule docs."""
    docs = {
        ".agent/operating-rules.md": [
            "# Operating Rules",
            "",
            MANAGED_MARKER,
            "",
            "## Execution Discipline",
            "",
            "- Preserve user-authored source plans by default.",
            "- Keep all updates consistent with the current source confidence.",
            "- Treat low-confidence intake as a clarification problem, not an implementation license.",
            "- Do not begin implementation after initialization unless the user explicitly asks for post-init execution.",
            "- Respect existing repository layout during repo-hydrate work.",
            "",
            "## Task Execution",
            "",
            "- Before starting a task, confirm it still advances the active goal in `goals/` and the current project definition in `PROJECT.md`.",
            "- Mark a task `in progress` only when execution actually starts.",
            "- Append to the task `Execution Log` only after a meaningful execution batch, milestone, blocker change, status change, or user-directed change of course.",
            "- Do not log every file save, every small refactor, formatting-only edits, or changes already obvious from git history.",
            "- When a task observation affects future work, update the task `Downstream Impact`, the active goal `Observation Ledger`, and `STATUS.md`.",
            "- Before marking a milestone done, run `python repo-init/scripts/lint_acceptance.py --repo .` or the equivalent repository-local command.",
            "",
            "## Decisions",
            "",
            "- Add to `DECISIONS.md` only when a durable decision is accepted.",
            "- Keep temporary feedback, exploratory notes, and unaccepted replan suggestions in `STATUS.md`, the active goal, or the current task.",
            "",
        ],
        ".agent/replanning.md": [
            "# Replanning Rules",
            "",
            MANAGED_MARKER,
            "",
            "## Autonomy",
            "",
            "- Tasks are provisional plans toward the active goal.",
            "- Agents may create, split, reorder, rewrite, or supersede planned and in-progress tasks when observations show a better route to the goal.",
            "- Agents may revise task acceptance criteria when the revision preserves the active goal and reflects execution evidence.",
            "- Completed task logs and historical observations are append-only; do not rewrite history to make the new plan look clean.",
            "- Milestone goals should stay few and human-readable; create a new milestone only when it clarifies a major project phase.",
            "",
            "## Human Confirmation Required",
            "",
            "- Changing the goal statement requires explicit human confirmation.",
            "- Changing hard constraints requires explicit human confirmation.",
            "- Changing durable project scope requires explicit human confirmation.",
            "- Changing accepted success criteria requires explicit human confirmation.",
            "- Deleting or weakening `acceptance.json` checks requires explicit human confirmation.",
            "- Changing the collaboration contract requires explicit human confirmation or a direct user request.",
            "",
            "## Replan Records",
            "",
            "- Record high-signal observations in the active goal `Observation Ledger`.",
            "- Record applied task replans in the active goal `Replan History`.",
            "- Update `STATUS.md` when active task, task impact, blockers, or next step changes.",
            "- Keep `DECISIONS.md` for durable accepted project decisions, not ordinary task replans.",
            "",
        ],
        ".agent/file-contract.md": [
            "# File Contract",
            "",
            MANAGED_MARKER,
            "",
            "## Responsibilities",
            "",
            "- `PROJECT.md` stores durable project definition, scope, constraints, and compatibility assumptions.",
            "- `goals/*.md` stores active execution goals, success criteria, planned tasks, observations, and replan history.",
            "- `tasks/*.md` stores provisional task plans, execution records, assumption checks, and downstream impact.",
            "- `acceptance.json` stores machine-checkable milestone acceptance criteria.",
            "- `STATUS.md` stores the current operational snapshot and next recommended step.",
            "- `DECISIONS.md` stores durable accepted decisions only.",
            "- `.agent/*.md` stores detailed collaboration rules.",
            "",
            "## Update Rules",
            "",
            "- Update `STATUS.md` when active goal, active task, latest feedback, task impact, recommended replan, blocker state, or next step changes.",
            "- Update the active goal when observations change the route to the goal or tasks are created, split, reordered, rewritten, or superseded.",
            "- Update a task when it is created, started, blocked, completed, superseded, or materially changed.",
            "- Add or strengthen `acceptance.json` checks when new machine-checkable acceptance gaps are discovered.",
            "- Do not remove or weaken `acceptance.json` checks without explicit human confirmation.",
            "- Update `PROJECT.md` only when project goals, scope, constraints, or success criteria change with the required human confirmation.",
            "",
            "## Storage Rules",
            "",
            "- Use links instead of duplicating long explanations across files.",
            "- Keep status short and current.",
            "- Keep task logs milestone-oriented and batch-oriented.",
            "- Do not create ad hoc notes outside `goals/`, `tasks/`, or `.agent/` for active implementation work without a clear reason.",
            "",
        ],
        ".agent/collaboration-rule-changes.md": [
            "# Collaboration Rule Changes",
            "",
            MANAGED_MARKER,
            "",
            "## Authority",
            "",
            "- Treat collaboration rules as project infrastructure, not normal task content.",
            "- If the user directly requests a rule change, update the relevant `.agent/*.md` file.",
            "- Adjust `AGENT.md` only when the thin index, reading order, or core invariants change.",
            "- Record accepted collaboration-rule changes in `DECISIONS.md`.",
            "",
            "## Proposals",
            "",
            "- If an agent observes rule friction without a direct user request, record the proposed rule change in the active goal or `STATUS.md`.",
            "- Wait for explicit human acceptance before changing the collaboration contract.",
            "- Do not bury rule-change proposals inside ordinary task logs only.",
            "",
            "## Boundary",
            "",
            "- Task replans are highly autonomous when they preserve the active goal.",
            "- Collaboration-contract changes are not autonomous; they require explicit user instruction or accepted confirmation.",
            "",
        ],
    }
    return {path: "\n".join(lines) for path, lines in docs.items()}


def render_acceptance(task_plan: TaskPlan) -> str:
    """Render acceptance.json content for generated milestone goals."""
    goals = []
    for goal_filename, _goal_content in task_plan["goal_files"]:
        goal_id = goal_id_from_filename(goal_filename)
        goal_entry: dict[str, Any] = {
            "id": goal_id,
            "file": f"goals/{goal_filename}",
            "status": "active" if goal_filename == task_plan["active_goal"] else "planned",
            "checks": [
                {
                    "id": f"{goal_id.lower()}-goal-file-exists",
                    "type": "files_exist",
                    "paths": [f"goals/{goal_filename}"],
                },
                {
                    "id": f"{goal_id.lower()}-goal-headings",
                    "type": "markdown_headings",
                    "paths": [f"goals/{goal_filename}"],
                    "headings": ["Final Outcome", "Human Acceptance", "Machine Acceptance", "Observation Ledger", "Replan History"],
                },
            ],
        }
        if goal_filename == task_plan["active_goal"]:
            goal_entry["checks"].extend(
                [
                    {
                        "id": f"{goal_id.lower()}-status-active-goal",
                        "type": "required_text",
                        "paths": ["STATUS.md"],
                        "patterns": [f"Active goal: `goals/{goal_filename}`"],
                    },
                    {
                        "id": f"{goal_id.lower()}-recommended-task-exists",
                        "type": "files_exist",
                        "paths": [f"tasks/{task_plan['recommended_start_task']}"] if task_plan["recommended_start_task"] else [],
                    },
                ]
            )
        goals.append(goal_entry)

    payload = {
        "version": 1,
        "managed_by": "RepoFrame",
        "active_goal": goal_id_from_filename(task_plan["active_goal"]),
        "active_goal_file": f"goals/{task_plan['active_goal']}",
        "linter": "repo-init/scripts/lint_acceptance.py",
        "goals": goals,
    }
    return json.dumps(payload, indent=2, ensure_ascii=False) + "\n"


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
    planning = intake.get("adaptive_task_planning") or {}
    active_goal = f"goals/{task_plan['active_goal']}"
    active_task = task_plan["active_task"] or "none"
    recommended_start = task_plan["recommended_start_task"]
    latest_feedback = [
        "No execution feedback recorded yet. Add 1-3 high-signal conclusions after the next meaningful execution batch."
    ]
    task_impact = [
        "No downstream task impact recorded yet. Record affected tasks as `keep | reorder | block | split | supersede | revise-acceptance | clarify` when feedback changes future work."
    ]
    if needs_clarification(intake):
        recommended_replan = [
            "Resolve the current clarification questions before starting implementation work.",
            "After clarification, rewrite planned tasks if the confirmed facts change the route to the goal.",
        ]
    elif planning.get("multi_task"):
        recommended_replan = [
            f"Start with `{recommended_start}` when the user asks for post-init execution.",
            "During execution, rewrite planned tasks autonomously when observations show a better route to the active goal.",
        ]
    else:
        recommended_replan = [
            f"Start with `{recommended_start}` when the user asks for post-init execution.",
            "Expand or rewrite tasks when fresh execution feedback shows the goal needs a different route.",
        ]

    if needs_clarification(intake):
        objective = "clarify the source bundle before any implementation work"
        next_step = f"review `{recommended_start}` and resolve the current open questions"
        state = "initialized from a source bundle that still needs clarification"
        status_value = "blocked"
        blockers = "unresolved source-bundle questions remain"
        risks = "any inferred scope may still be speculative"
    elif mode == "greenfield":
        objective = f"deliver the initial {summary['project_type']} goal"
        next_step = f"start `{recommended_start}` only when the user explicitly asks for post-init execution"
        state = "repository initialized from a prompt-only brief with an active goal and planned tasks"
        status_value = "not started"
        blockers = "none"
        risks = "scope details may still need confirmation during execution"
    elif mode == "repo-hydrate":
        objective = "align the existing repository with the active goal and collaboration workflow"
        next_step = f"start `{recommended_start}` only when the user explicitly asks for post-init execution"
        state = "collaboration layer added to an existing repository with an active goal and planned tasks"
        status_value = "not started"
        blockers = "none"
        risks = "repository-to-goal mapping may shift after the first audit batch"
    else:
        objective = "translate the imported source plan into the first implementation step"
        next_step = f"start `{recommended_start}` only when the user explicitly asks for post-init execution"
        state = "collaboration layer created from an imported project plan with an active goal and planned tasks"
        status_value = "not started"
        blockers = "none"
        risks = "scope details still need confirmation"

    recently_completed = (
        f"- initialization created `{len(task_plan['milestone_goals'])}` milestone goal(s), acceptance file `acceptance.json`, and `{len(task_plan['planned_tasks'])}` planned task(s)"
    )

    lines = [
        "# STATUS.md",
        "",
        MANAGED_MARKER,
        "",
        "## Current Focus",
        "",
        f"- Active goal: `{active_goal}`",
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
            "Keep temporary feedback notes and unaccepted replan suggestions in `STATUS.md`, the active goal, or the current task instead of here.",
            "",
            "No durable project decisions were established during initialization.",
            "",
        ]
    )
