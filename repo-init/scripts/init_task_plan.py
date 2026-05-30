#!/usr/bin/env python3
"""Goal and task planning helpers for repo initialization."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, TypedDict

from init_summary import needs_clarification, source_reference
from repo_init_common import MANAGED_MARKER, normalize_text, slugify, unique


COMPLEXITY_KEYWORDS = ("api", "integration", "database", "auth", "sync", "queue", "pipeline", "storage", "service")


class TaskPlan(TypedDict):
    """Structured goal-centric work-plan output for rendering and writing."""

    goal_files: list[tuple[str, str]]
    files: list[tuple[str, str]]
    active_goal: str
    active_task: str | None
    recommended_start_task: str
    goal_file: str
    milestone_goals: list[str]
    planned_tasks: list[str]
    acceptance_file: str
    adaptive_planning_applied: bool
    master_task: str | None
    child_tasks: list[str]
    decomposition_applied: bool


def next_number(repo_root: Path, directory_name: str, prefix: str) -> int:
    """Return the next available numbered artifact id for a directory."""
    existing_ids = [0]
    target_dir = repo_root / directory_name
    if target_dir.exists():
        for path in target_dir.glob(f"{prefix}-*.md"):
            match = re.match(rf"{re.escape(prefix)}-(\d+)", path.name)
            if match:
                existing_ids.append(int(match.group(1)))
    return max(existing_ids) + 1


def next_task_number(repo_root: Path) -> int:
    """Return the next available task number."""
    return next_number(repo_root, "tasks", "TASK")


def next_goal_number(repo_root: Path) -> int:
    """Return the next available goal number."""
    return next_number(repo_root, "goals", "GOAL")


def task_filename(task_number: int, title: str) -> str:
    """Build a stable task filename."""
    return f"TASK-{task_number:03d}-{slugify(title)}.md"


def goal_filename(goal_number: int, title: str) -> str:
    """Build a stable goal filename."""
    return f"GOAL-{goal_number:03d}-{slugify(title)}.md"


def artifact_id_from_filename(filename: str, prefix: str, fallback: str) -> str:
    """Extract a numbered artifact id prefix from a filename."""
    match = re.match(rf"({re.escape(prefix)}-\d+)", filename)
    return match.group(1) if match else fallback


def task_id_from_filename(filename: str) -> str:
    """Extract the task id prefix from a filename."""
    return artifact_id_from_filename(filename, "TASK", "TASK-000")


def goal_id_from_filename(filename: str) -> str:
    """Extract the goal id prefix from a filename."""
    return artifact_id_from_filename(filename, "GOAL", "GOAL-000")


def bundle_word_count(intake: dict[str, Any]) -> int:
    """Return a bundle-level word count."""
    sources = intake.get("sources") or []
    if sources:
        return sum(int(entry.get("word_count") or 0) for entry in sources)
    return int(intake.get("word_count") or 0)


def has_integration_evidence(intake: dict[str, Any]) -> bool:
    """Return True when the intake suggests a data or integration slice."""
    stack = (intake.get("merged_snapshot") or {}).get("stack") or []
    if len(stack) >= 3:
        return True

    combined = " ".join(
        [
            *(intake.get("sections") or []),
            normalize_text(intake.get("extracted_text") or ""),
            *(normalize_text(f"{entry.get('label', '')} {entry.get('title', '')}") for entry in intake.get("sources") or []),
        ]
    ).lower()
    if any(keyword in combined for keyword in COMPLEXITY_KEYWORDS):
        return True

    sources = intake.get("sources") or []
    if len(sources) < 2:
        return False
    label_blob = " ".join(
        normalize_text(f"{entry.get('label', '')} {entry.get('title', '')}").lower() for entry in sources
    )
    matched = [keyword for keyword in COMPLEXITY_KEYWORDS if keyword in label_blob]
    return len(unique(matched)) >= 2


def clearly_segmented_repo(repo_summary: dict[str, Any]) -> bool:
    """Return True when the existing repository is large enough to justify extra hydrate slices."""
    return repo_summary.get("code_file_count", 0) >= 15 or repo_summary.get("meaningful_file_count", 0) >= 35


def very_large_repo(repo_summary: dict[str, Any]) -> bool:
    """Return True when the existing repository is very large and should allow extra split points."""
    return repo_summary.get("code_file_count", 0) >= 25 or repo_summary.get("meaningful_file_count", 0) >= 60


def assess_complexity(mode: str, intake: dict[str, Any], repo_summary: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    """Assess whether initialization should create a broader adaptive task plan."""
    if needs_clarification(intake):
        assessment = {
            "level": "simple",
            "score": 0,
            "signals": ["clarification-first"],
        }
        planning = {
            "applied": True,
            "multi_task": False,
            "reason": "Clarification-first input keeps initial planning to a clarification task until project facts are resolved.",
        }
        return assessment, planning

    signals: list[str] = []
    if intake.get("source_count", 0) >= 2:
        signals.append("source_count>=2")
    if len(intake.get("sections") or []) >= 6:
        signals.append("len(sections)>=6")
    if bundle_word_count(intake) >= 1200:
        signals.append("bundle_word_count>=1200")
    if len((intake.get("merged_snapshot") or {}).get("stack") or []) >= 3:
        signals.append("len(merged_snapshot.stack)>=3")
    if len((intake.get("merged_snapshot") or {}).get("constraints") or []) >= 3:
        signals.append("len(merged_snapshot.constraints)>=3")
    if repo_summary.get("code_file_count", 0) >= 8:
        signals.append("repo_summary.code_file_count>=8")
    if repo_summary.get("meaningful_file_count", 0) >= 20:
        signals.append("repo_summary.meaningful_file_count>=20")

    score = len(signals)
    hydrate_shortcut = mode == "repo-hydrate" and (
        repo_summary.get("code_file_count", 0) >= 8 or repo_summary.get("meaningful_file_count", 0) >= 20
    )
    level = "complex" if score >= 4 or hydrate_shortcut else "simple"
    assessment = {
        "level": level,
        "score": score,
        "signals": signals,
    }
    if hydrate_shortcut:
        reason = "Repo-hydrate repository size crosses the adaptive multi-task planning shortcut threshold."
    elif level == "complex":
        reason = "Complexity signals justify an adaptive multi-task plan."
    else:
        reason = "Complexity signals stayed low enough for a single planned starting task."
    planning = {
        "applied": True,
        "multi_task": level == "complex",
        "reason": reason,
    }
    return assessment, planning


def append_bulleted_subsection(body: list[str], title: str, items: list[str] | None = None) -> None:
    """Append a titled markdown subsection with bullet items."""
    body.extend(["", f"### {title}", ""])
    if items:
        body.extend([f"- {item}" for item in items])
    else:
        body.append("- none")


def build_task_document(
    *,
    title: str,
    filename: str,
    goal_ref: str,
    why: str,
    in_scope: list[str],
    out_of_scope: list[str],
    acceptance: list[str],
    files_dep: list[str],
    decisions_dep: list[str],
    external_dep: list[str],
    plan: list[str],
    facts: list[str],
    assumptions: list[str],
    risks: list[str],
    assumption_validated: list[str] | None = None,
    assumption_invalidated: list[str] | None = None,
    assumption_still_open: list[str] | None = None,
    downstream_affected: list[str] | None = None,
    downstream_follow_up: list[str] | None = None,
    extra_sections: list[tuple[str, list[str]]] | None = None,
) -> str:
    """Render a planned task markdown document."""
    extra_sections = extra_sections or []
    still_open = assumptions if assumption_still_open is None else assumption_still_open
    body = [
        f"# {title}",
        "",
        MANAGED_MARKER,
        "",
        "## Metadata",
        "",
        f"- ID: `{task_id_from_filename(filename)}`",
        "- Status: `planned`",
        "- Owner: `shared`",
        f"- Goal: `{goal_ref}`",
        "- Created: `2026-04-22`",
        "- Updated: `2026-04-22`",
        "",
        "## Why",
        "",
        why,
        "",
        "## Scope",
        "",
    ]
    body.extend([f"- In scope: {item}" for item in in_scope])
    body.extend([f"- Out of scope: {item}" for item in out_of_scope])
    body.extend(["", "## Acceptance Criteria", ""])
    body.extend([f"- {item}" for item in acceptance])
    body.extend(["", "## Dependencies", ""])
    body.append(f"- Files: `{', '.join(files_dep) if files_dep else 'none'}`")
    body.append(f"- Decisions: `{', '.join(decisions_dep) if decisions_dep else 'none'}`")
    body.append(f"- External: `{', '.join(external_dep) if external_dep else 'none'}`")
    body.extend(["", "## Plan", ""])
    body.extend([f"{index}. {step}" for index, step in enumerate(plan, start=1)])

    for section_title, lines in extra_sections:
        body.extend(["", f"## {section_title}", ""])
        body.extend(lines or ["- none"])

    body.extend(["", "## Notes", ""])
    body.append(f"- Facts: {'; '.join(facts) if facts else 'none'}")
    body.append(f"- Assumptions: {'; '.join(assumptions) if assumptions else 'none'}")
    body.append(f"- Risks: {'; '.join(risks) if risks else 'none'}")
    body.extend(
        [
            "",
            "## Assumption Checks",
            "",
            "Update these lists whenever current execution validates or invalidates the task's working assumptions.",
        ]
    )
    append_bulleted_subsection(body, "Validated", assumption_validated)
    append_bulleted_subsection(body, "Invalidated", assumption_invalidated)
    append_bulleted_subsection(body, "Still Open", still_open)
    body.extend(
        [
            "",
            "## Downstream Impact",
            "",
            "If execution changes later work, mirror that impact here and in the active goal instead of leaving it only in `Execution Log`.",
        ]
    )
    append_bulleted_subsection(body, "Affected Tasks", downstream_affected)
    append_bulleted_subsection(body, "Suggested Follow-up", downstream_follow_up)
    body.extend(
        [
            "",
            "## Execution Log",
            "",
            "Record milestone-level progress here. Each entry should summarize one meaningful execution batch, task-status transition, blocker change, replan, or user-directed change of course.",
            "",
            "Do not log every file save, every tiny edit, or every formatting-only change.",
            "",
            "- `2026-04-22`: task planned during repository initialization",
            "",
        ]
    )
    return "\n".join(body)


def build_goal_document(
    *,
    title: str,
    filename: str,
    status: str,
    mode: str,
    summary: dict[str, Any],
    source_ref: str,
    planning: dict[str, Any],
    planned_tasks: list[dict[str, str]],
    recommended_start_task: str,
    final_outcome: str | None = None,
) -> str:
    """Render a milestone goal markdown document."""
    constraints = summary.get("constraints") or ["Clarify additional constraints during execution."]
    assumptions = summary.get("assumptions") or ["The initial execution strategy may change as task observations arrive."]
    task_lines = [f"- `{item['filename']}`: {item['goal']}" for item in planned_tasks] or ["- none"]
    human_acceptance = [
        "A human can confirm this milestone advances the project outcome described in `PROJECT.md`.",
        "Known limitations and unresolved questions are explicit before the next milestone starts.",
        "Any change to the milestone outcome, hard constraints, durable scope, or accepted success criteria has explicit human confirmation.",
    ]
    body = [
        f"# {title}",
        "",
        MANAGED_MARKER,
        "",
        "## Metadata",
        "",
        f"- ID: `{goal_id_from_filename(filename)}`",
        f"- Status: `{status}`",
        "- Type: `milestone`",
        f"- Mode: `{mode}`",
        f"- Source: `{source_ref}`",
        "- Created: `2026-04-22`",
        "- Updated: `2026-04-22`",
        "",
        "## Final Outcome",
        "",
        final_outcome or summary.get("goal") or "Clarify and achieve the primary project outcome.",
        "",
        "## Human Acceptance",
        "",
    ]
    body.extend([f"- {item}" for item in human_acceptance])
    body.extend(["", "## Machine Acceptance", "", f"- See `acceptance.json` goal `{goal_id_from_filename(filename)}`."])
    body.extend(["", "## Constraints", ""])
    body.extend([f"- {item}" for item in constraints])
    body.extend(["", "## Current Strategy", ""])
    if status == "active" and planning.get("multi_task"):
        body.append("- Use the planned tasks as the first execution strategy, then rewrite task order or task definitions when observations show a better route to the goal.")
    elif status == "active":
        body.append("- Use the planned starting task as the first execution strategy, then expand or rewrite tasks when observations show the goal needs a different route.")
    else:
        body.append("- Keep this milestone planned until the active milestone is complete or explicitly changed.")
    body.append("- Preserve the goal, hard constraints, durable project scope, and accepted success criteria unless the user confirms a change.")
    body.extend(["", "## Planned Tasks", ""])
    body.extend(task_lines)
    body.extend(
        [
            "",
            "## Recommended Start",
            "",
            f"- `{recommended_start_task}`" if recommended_start_task else "- none",
            "",
            "## Observation Ledger",
            "",
            "- No execution observations recorded yet.",
            "- Use: `Date=<YYYY-MM-DD>; Source=<task-id or human>; Observation=<high-signal fact>; Impact=<keep|reorder|block|split|supersede|revise-acceptance|clarify>; Follow-up=<task or rule change>`",
            "",
            "## Replan History",
            "",
            "- none accepted yet",
            "- Task replans may be applied autonomously when they keep moving toward this goal.",
            "- Goal, hard-constraint, durable-scope, accepted-success-criteria, and collaboration-contract changes require explicit human confirmation.",
            "",
            "## Assumptions",
            "",
        ]
    )
    body.extend([f"- {item}" for item in assumptions])
    body.extend(
        [
            "",
            "## Initialization Hold",
            "",
            "- Repository initialization created milestone goals and planned tasks only.",
            "- Do not begin implementation in the same initialization turn unless the user explicitly asks for post-init execution.",
            "",
        ]
    )
    return "\n".join(body)


def simple_task_specs(mode: str, intake: dict[str, Any]) -> list[dict[str, Any]]:
    """Build the single planned task for simple or clarification-first initialization."""
    questions = intake.get("clarification_questions") or []
    if mode == "greenfield":
        return [
            {
                "title": "Bootstrap initial project scaffold",
                "goal": "Create the first implementation scaffold from the initial project brief.",
                "plan": ["Set up the minimal project skeleton.", "Confirm the first user-facing workflow.", "Prepare the next implementation task."],
                "risk": "scope details still need confirmation",
            }
        ]
    if mode == "repo-hydrate":
        return [
            {
                "title": "Align existing repository with collaboration workflow",
                "goal": "Align the existing repository with the new collaboration layer and identify the next concrete implementation step.",
                "plan": ["Review the existing code footprint.", "Map current code to project goals.", "Choose the next safe implementation increment."],
                "risk": "the current repository-to-goal mapping may shift after the first audit batch",
            }
        ]
    if needs_clarification(intake):
        return [
            {
                "title": "Clarify source bundle and recover missing scope",
                "goal": "Resolve missing or low-confidence project facts before scheduling implementation work.",
                "plan": ["Review the source bundle and conflicts.", "Confirm unresolved project facts with the user.", "Only then schedule implementation work."],
                "risk": "unresolved source questions must be answered before implementation work can be sequenced safely",
                "questions": questions[:5],
            }
        ]
    return [
        {
            "title": "Clarify initial scope and implementation order",
            "goal": "Translate the imported project plan into a clear first implementation sequence.",
            "plan": ["Review the imported plan.", "Confirm the MVP scope and constraints.", "Choose the first implementation milestone."],
            "risk": "the imported plan may still need scope and milestone confirmation before execution starts",
        }
    ]


def adaptive_task_specs(mode: str, intake: dict[str, Any], repo_summary: dict[str, Any]) -> list[dict[str, Any]]:
    """Build evidence-backed planned task specs for a broader initial strategy."""
    if mode == "greenfield":
        specs = [
            {"title": "Scope and architecture lock", "goal": "Lock the initial scope, architecture boundaries, and first delivery sequence."},
            {"title": "Repository scaffold and runtime setup", "goal": "Set up the repository skeleton, runtime, tooling, and baseline developer workflow."},
            {"title": "Primary workflow or MVP slice", "goal": "Define and deliver the first end-to-end user workflow or MVP slice."},
            {"title": "Quality and validation baseline", "goal": "Establish the first test, validation, and release-safety guardrails."},
        ]
        if has_integration_evidence(intake):
            specs.append({"title": "Data or integration slice", "goal": "Define and implement the first data boundary or integration surface needed by the MVP."})
        return specs

    if mode == "plan-ingest":
        specs = [
            {"title": "Imported scope normalization", "goal": "Normalize the imported plan into a stable execution scope and explicit implementation order."},
            {"title": "Architecture and repository shape", "goal": "Map the imported plan to the intended repository structure and technical boundaries."},
            {"title": "Primary implementation slice", "goal": "Prepare the highest-value implementation slice from the imported plan."},
            {"title": "Quality, validation, and release safety", "goal": "Establish the minimum validation and release-safety baseline for the imported scope."},
        ]
        if has_integration_evidence(intake):
            specs.append({"title": "Data or integration slice", "goal": "Isolate the first data flow or external integration slice required by the imported plan."})
        return specs

    specs = [
        {"title": "Current-state audit and target mapping", "goal": "Audit the current repository and map existing code to the intended hydration target."},
        {"title": "Hydration alignment of docs and workflow", "goal": "Align repository docs, workflow files, and task structure with the intended collaboration model."},
        {"title": "Highest-value implementation or refactor slice", "goal": "Identify and prepare the highest-value implementation or refactor slice in the existing codebase."},
        {"title": "Regression and validation safety", "goal": "Define the validation baseline needed to hydrate the repository without introducing regressions."},
    ]
    if has_integration_evidence(intake):
        specs.append({"title": "Integration or subsystem split", "goal": "Separate the first integration-heavy or subsystem-specific slice from the broader hydrate effort."})
    if clearly_segmented_repo(repo_summary):
        specs.append({"title": "Secondary subsystem stabilization slice", "goal": "Prepare a second subsystem-focused slice so the hydrate plan reflects the repository's existing segmentation."})
    if very_large_repo(repo_summary):
        specs.append({"title": "Cross-cutting platform or infrastructure slice", "goal": "Capture platform, tooling, or infrastructure work that should remain separate from feature slices."})
    return specs


def build_planned_task_specs(mode: str, intake: dict[str, Any], repo_summary: dict[str, Any]) -> list[dict[str, Any]]:
    """Build the planned tasks for initialization without enforcing a fixed count."""
    planning = intake.get("adaptive_task_planning") or intake.get("task_decomposition") or {}
    if not planning.get("multi_task") or needs_clarification(intake):
        return simple_task_specs(mode, intake)
    return adaptive_task_specs(mode, intake, repo_summary)


def goal_title_for(mode: str, summary: dict[str, Any]) -> str:
    """Build a concise fallback active-goal title."""
    name = concise_goal_subject(mode, summary)
    if mode == "repo-hydrate":
        return f"Align {name} with the target outcome"
    if mode == "plan-ingest":
        return f"Execute {name} from the imported plan"
    return f"Deliver {name}"


def concise_goal_subject(mode: str, summary: dict[str, Any]) -> str:
    """Return a short subject for milestone goal titles."""
    name = normalize_text(summary.get("name") or "")
    if not name:
        return "repository" if mode == "repo-hydrate" else "project"
    if len(name) > 48 or len(name.split()) > 6:
        return "repository" if mode == "repo-hydrate" else "project"
    return name


def build_milestone_goal_specs(
    mode: str,
    intake: dict[str, Any],
    repo_summary: dict[str, Any],
    summary: dict[str, Any],
) -> list[dict[str, str]]:
    """Build a compact milestone goal list without introducing goal hierarchy."""
    name = concise_goal_subject(mode, summary)
    primary_goal = summary.get("goal") or "Clarify and achieve the primary project outcome."
    planning = intake.get("adaptive_task_planning") or {}
    if needs_clarification(intake):
        return [
            {
                "title": f"Scope clarified for {name}",
                "status": "active",
                "outcome": "Resolve missing or low-confidence project facts before implementation starts.",
            }
        ]
    if not planning.get("multi_task"):
        return [
            {
                "title": goal_title_for(mode, summary),
                "status": "active",
                "outcome": primary_goal,
            }
        ]

    if mode == "repo-hydrate":
        specs = [
            {"title": f"Current state mapped for {name}", "status": "active", "outcome": "The current repository is mapped to the target outcome and the safest first implementation route is clear."},
            {"title": f"Hydration changes ready for {name}", "status": "planned", "outcome": "The repository collaboration workflow and highest-value implementation or refactor slice are ready."},
            {"title": f"Regression safety ready for {name}", "status": "planned", "outcome": "Validation and regression checks are sufficient for continued repository work."},
        ]
        if clearly_segmented_repo(repo_summary):
            specs.append({"title": f"Subsystem stabilization ready for {name}", "status": "planned", "outcome": "Important repository subsystems have stable boundaries and follow-up work is explicit."})
        return specs[:4]

    if mode == "plan-ingest":
        specs = [
            {"title": f"Imported scope ready for {name}", "status": "active", "outcome": "The imported plan is normalized into a stable milestone scope and execution order."},
            {"title": f"Implementation slice ready for {name}", "status": "planned", "outcome": "The highest-value implementation slice from the imported plan is prepared and validated."},
            {"title": f"Validation baseline ready for {name}", "status": "planned", "outcome": "The imported scope has a minimum validation and release-safety baseline."},
        ]
        if has_integration_evidence(intake):
            specs.insert(2, {"title": f"Integration slice ready for {name}", "status": "planned", "outcome": "The first required data flow or external integration slice is isolated and ready."})
        return specs[:4]

    specs = [
        {"title": f"MVP ready for {name}", "status": "active", "outcome": primary_goal},
        {"title": f"Validation baseline ready for {name}", "status": "planned", "outcome": "The initial implementation has a reliable validation baseline."},
        {"title": f"Release handoff ready for {name}", "status": "planned", "outcome": "The project is ready for the next release or handoff milestone."},
    ]
    if has_integration_evidence(intake):
        specs.insert(1, {"title": f"Integration milestone ready for {name}", "status": "planned", "outcome": "The first required integration or data boundary is implemented and validated."})
    return specs[:4]


def render_task_set(
    repo_root: Path,
    mode: str,
    intake: dict[str, Any],
    repo_summary: dict[str, Any],
    summary: dict[str, Any],
) -> TaskPlan:
    """Render the active goal and its initial planned tasks."""
    source_ref = source_reference(intake)
    planning = intake.get("adaptive_task_planning") or intake.get("task_decomposition") or {"applied": True, "multi_task": False}
    task_specs = build_planned_task_specs(mode, intake, repo_summary)
    goal_specs = build_milestone_goal_specs(mode, intake, repo_summary, summary)
    start_goal_number = next_goal_number(repo_root)
    milestone_goals: list[dict[str, str]] = []
    for offset, spec in enumerate(goal_specs):
        filename = goal_filename(start_goal_number + offset, spec["title"])
        milestone_goals.append({**spec, "filename": filename})
    goal_file = milestone_goals[0]["filename"]
    goal_ref = goal_file

    start_number = next_task_number(repo_root)
    planned_tasks: list[dict[str, str]] = []
    rendered_tasks: list[tuple[str, str]] = []
    for offset, spec in enumerate(task_specs):
        filename = task_filename(start_number + offset, spec["title"])
        planned_tasks.append({"filename": filename, "title": spec["title"], "goal": spec["goal"]})

    recommended_start = planned_tasks[0]["filename"] if planned_tasks else ""
    for index, item in enumerate(planned_tasks, start=1):
        related = []
        if index > 1:
            related.append(f"- Review `{planned_tasks[index - 2]['filename']}` for upstream context before execution.")
        if index < len(planned_tasks):
            related.append(f"- Coordinate boundaries with `{planned_tasks[index]['filename']}` before handoff.")
        if not related:
            related.append("- No adjacent planned-task dependency was inferred during initialization.")

        spec = task_specs[index - 1]
        question_lines = [f"- {question}" for question in spec.get("questions", [])]
        extra_sections = [
            ("Goal Alignment", [f"- Goal file: `{goal_file}`", "- This task is a provisional route toward the goal, not a durable scope boundary."]),
            (
                "Replanning Notes",
                [
                    "- Agents may rewrite, split, reorder, or supersede this task when observations show a better route to the goal.",
                    "- Goal, hard-constraint, durable-scope, accepted-success-criteria, and collaboration-contract changes require explicit human confirmation.",
                ],
            ),
            ("Related Planned Tasks", related),
        ]
        if question_lines:
            extra_sections.append(("Open Questions", question_lines))

        content = build_task_document(
            title=item["title"],
            filename=item["filename"],
            goal_ref=goal_ref,
            why=item["goal"],
            in_scope=[item["goal"], "preserve observations that affect the active goal or later tasks"],
            out_of_scope=["changing the goal or hard constraints without explicit human confirmation", "starting unrelated implementation slices"],
            acceptance=[
                "This task advances the active goal or produces a clear observation that changes the route to it.",
                "Dependencies, assumptions, and validation expectations are explicit before execution begins.",
                "Any replan-worthy observation is recorded in this task and the active goal.",
            ],
            files_dep=["PROJECT.md", "STATUS.md", f"goals/{goal_file}", source_ref],
            decisions_dep=[],
            external_dep=[],
            plan=spec.get(
                "plan",
                [
                    f"Review `{goal_file}`, `PROJECT.md`, and `STATUS.md` for current context.",
                    f"Prepare the concrete implementation approach for `{item['title']}`.",
                    f"Execute and validate `{item['title']}` once this task is explicitly started.",
                ],
            ),
            facts=[f"goal file is `goals/{goal_file}`", f"recommended order position is `{index}`"],
            assumptions=["this task remains `planned` until a human or agent explicitly starts it"],
            risks=[spec.get("risk", "execution observations may change task order, scope, or acceptance expectations")],
            assumption_still_open=["Execution feedback from this task may change later planned tasks or create new tasks."],
            downstream_follow_up=[
                f"If this task affects later work, update `goals/{goal_file}` `Observation Ledger` and `STATUS.md` before changing downstream tasks.",
            ],
            extra_sections=extra_sections,
        )
        rendered_tasks.append((item["filename"], content))

    goal_files: list[tuple[str, str]] = []
    for goal_item in milestone_goals:
        goal_task_list = planned_tasks if goal_item["filename"] == goal_file else []
        goal_recommended_start = recommended_start if goal_item["filename"] == goal_file else ""
        goal_content = build_goal_document(
            title=goal_item["title"],
            filename=goal_item["filename"],
            status=goal_item["status"],
            mode=mode,
            summary=summary,
            source_ref=source_ref,
            planning=planning,
            planned_tasks=goal_task_list,
            recommended_start_task=goal_recommended_start,
            final_outcome=goal_item.get("outcome"),
        )
        goal_files.append((goal_item["filename"], goal_content))
    planned_filenames = [item["filename"] for item in planned_tasks]
    milestone_filenames = [item["filename"] for item in milestone_goals]
    multi_task = bool(planning.get("multi_task"))
    return {
        "goal_files": goal_files,
        "files": rendered_tasks,
        "active_goal": goal_file,
        "active_task": None,
        "recommended_start_task": recommended_start,
        "goal_file": goal_file,
        "milestone_goals": milestone_filenames,
        "planned_tasks": planned_filenames,
        "acceptance_file": "acceptance.json",
        "adaptive_planning_applied": True,
        "master_task": None,
        "child_tasks": planned_filenames if multi_task else [],
        "decomposition_applied": multi_task,
    }
