#!/usr/bin/env python3
"""Task planning and complexity helpers for repo initialization."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, TypedDict

from init_summary import needs_clarification, source_reference
from repo_init_common import MANAGED_MARKER, normalize_text, slugify, unique


COMPLEXITY_KEYWORDS = ("api", "integration", "database", "auth", "sync", "queue", "pipeline", "storage", "service")


class TaskPlan(TypedDict):
    """Structured task-plan output for initialization rendering and writing."""

    files: list[tuple[str, str]]
    active_task: str
    recommended_start_task: str
    master_task: str | None
    child_tasks: list[str]
    decomposition_applied: bool


def next_task_number(repo_root: Path) -> int:
    """Return the next available task number."""
    existing_ids = [0]
    tasks_dir = repo_root / "tasks"
    if tasks_dir.exists():
        for path in tasks_dir.glob("TASK-*.md"):
            match = re.match(r"TASK-(\d+)", path.name)
            if match:
                existing_ids.append(int(match.group(1)))
    return max(existing_ids) + 1


def task_filename(task_number: int, title: str) -> str:
    """Build a stable task filename."""
    return f"TASK-{task_number:03d}-{slugify(title)}.md"


def task_id_from_filename(filename: str) -> str:
    """Extract the task id prefix from a filename."""
    match = re.match(r"(TASK-\d+)", filename)
    return match.group(1) if match else "TASK-000"


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
    """Return True when the existing repository is very large and should allow an extra split."""
    return repo_summary.get("code_file_count", 0) >= 25 or repo_summary.get("meaningful_file_count", 0) >= 60


def assess_complexity(mode: str, intake: dict[str, Any], repo_summary: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    """Assess whether initialization should decompose into a task set."""
    if needs_clarification(intake):
        assessment = {
            "level": "simple",
            "score": 0,
            "signals": ["clarification-first"],
        }
        decomposition = {
            "applied": False,
            "reason": "Clarification-first input blocks multi-task decomposition until project facts are resolved.",
        }
        return assessment, decomposition

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
        reason = "Repo-hydrate repository size crosses the auto-decomposition shortcut threshold."
    elif level == "complex":
        reason = "Complexity signals meet the auto-decomposition threshold."
    else:
        reason = "Complexity signals stayed below the auto-decomposition threshold."
    decomposition = {
        "applied": level == "complex",
        "reason": reason,
    }
    return assessment, decomposition


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
    parent_id: str | None = None,
) -> str:
    """Render a task markdown document."""
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
        "- Status: `todo`",
        "- Owner: `shared`",
    ]
    if parent_id:
        body.append(f"- Parent: `{parent_id}`")
    body.extend(
        [
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
    )
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

    body.extend(
        [
            "",
            "## Open Source Reuse Check",
            "",
            "- Required: `yes when this task introduces a reusable technical capability; otherwise no`",
            "- Search keywords: `record planned searches before implementation`",
            "- Candidate projects: `record links or none found`",
            "- Decision: `Direct Use | Adapt | Learn From | Build In-House | not required yet`",
            "- Reason: `explain the reuse decision before implementation starts`",
        ]
    )

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
            "If execution changes downstream work, mirror that impact here instead of leaving it only in `Execution Log`.",
        ]
    )
    append_bulleted_subsection(body, "Affected Tasks", downstream_affected)
    append_bulleted_subsection(body, "Suggested Follow-up", downstream_follow_up)
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
    return "\n".join(body)


def build_child_task_specs(mode: str, intake: dict[str, Any], repo_summary: dict[str, Any]) -> list[dict[str, str]]:
    """Build task-family specs for a complex project."""
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
    return specs[:7]


def render_simple_task_set(repo_root: Path, mode: str, intake: dict[str, Any]) -> TaskPlan:
    """Render the default single-task initialization output."""
    source_ref = source_reference(intake)
    questions = intake.get("clarification_questions") or []
    task_number = next_task_number(repo_root)

    if mode == "greenfield":
        title = "Bootstrap initial project scaffold"
        why = "Create the first implementation scaffold from the initial project brief."
        plan = ["Set up the minimal project skeleton.", "Confirm the first user-facing workflow.", "Prepare the next implementation task."]
        assumption_still_open = ["The initial workflow and delivery sequence may change once the first implementation batch is reviewed."]
        downstream_follow_up = [
            "Update `STATUS.md` with the latest feedback before changing the next implementation slice.",
            "If execution changes scope, blockers, or acceptance criteria, record the downstream impact before revising later work.",
        ]
    elif mode == "repo-hydrate":
        title = "Align existing repository with collaboration workflow"
        why = "Align the existing repository with the new collaboration layer and identify the next concrete implementation step."
        plan = ["Review the existing code footprint.", "Map current code to project goals.", "Choose the next safe implementation increment."]
        assumption_still_open = ["The current repository-to-goal mapping may shift after the first audit batch."]
        downstream_follow_up = [
            "Update `STATUS.md` with audit findings before reprioritizing follow-on implementation work.",
            "If the audit changes the safest next slice, record the downstream impact before revising later tasks.",
        ]
    elif needs_clarification(intake):
        title = "Clarify source bundle and recover missing scope"
        why = "The source bundle still contains unresolved questions or low-confidence extraction."
        plan = ["Review the source bundle and conflicts.", "Confirm unresolved project facts with the user.", "Only then schedule implementation work."]
        assumption_still_open = ["The unresolved source questions must be answered before implementation work can be sequenced safely."]
        downstream_follow_up = [
            "Resolve clarification questions before creating or reprioritizing implementation tasks.",
            "Update `STATUS.md` once the missing scope facts are confirmed.",
        ]
    else:
        title = "Clarify initial scope and implementation order"
        why = "Translate the imported project plan into a clear first implementation sequence."
        plan = ["Review the imported plan.", "Confirm the MVP scope and constraints.", "Choose the first implementation milestone."]
        assumption_still_open = ["The imported plan may still need scope and milestone confirmation before execution starts."]
        downstream_follow_up = [
            "Update `STATUS.md` with the latest scope confirmation before revising downstream work.",
            "If new constraints or blockers appear, record the downstream impact before changing later tasks.",
        ]

    filename = task_filename(task_number, title)
    content = build_task_document(
        title=title,
        filename=filename,
        why=why,
        in_scope=["establish the next safe implementation step", "align execution with the current project definition"],
        out_of_scope=["broad speculative feature expansion"],
        acceptance=[
            "The next implementation step is clear.",
            "The task aligns with the current project definition and constraints.",
            "Open questions are explicit rather than hidden in assumptions.",
        ],
        files_dep=[source_ref],
        decisions_dep=[],
        external_dep=[],
        plan=plan,
        facts=[f"initialization mode is `{mode}`", f"source count is `{intake.get('source_count', 0)}`"],
        assumptions=[f"intake confidence is `{intake.get('bundle_confidence', intake.get('confidence'))}`"],
        risks=["unresolved conflicts or low-confidence extraction remain" if needs_clarification(intake) else "scope still needs confirmation"],
        assumption_still_open=assumption_still_open,
        downstream_follow_up=downstream_follow_up,
        extra_sections=[("Open Questions", [f"- {question}" for question in questions[:5]])] if questions else [],
    )
    return {
        "files": [(filename, content)],
        "active_task": filename,
        "recommended_start_task": filename,
        "master_task": None,
        "child_tasks": [],
        "decomposition_applied": False,
    }


def render_decomposed_task_set(
    repo_root: Path,
    mode: str,
    intake: dict[str, Any],
    repo_summary: dict[str, Any],
    summary: dict[str, Any],
) -> TaskPlan:
    """Render a coordinating master task plus child tasks for complex projects."""
    del summary  # Task planning does not currently use the merged summary directly.

    start_number = next_task_number(repo_root)
    source_ref = source_reference(intake)
    complexity = intake.get("complexity_assessment") or {}
    decomposition = intake.get("task_decomposition") or {}
    child_specs = build_child_task_specs(mode, intake, repo_summary)

    if mode == "greenfield":
        master_title = "Coordinate initial delivery plan"
        master_why = "Coordinate the first-wave task set for a complex greenfield initialization without starting implementation during initialization."
    elif mode == "repo-hydrate":
        master_title = "Coordinate repository hydration plan"
        master_why = "Coordinate the first-wave hydrate tasks so the existing repository can be aligned safely without collapsing everything into one task."
    else:
        master_title = "Coordinate imported plan execution"
        master_why = "Coordinate the imported-plan execution slices so the initial work is decomposed before implementation begins."

    master_filename = task_filename(start_number, master_title)
    child_tasks: list[dict[str, Any]] = []
    for offset, spec in enumerate(child_specs, start=1):
        number = start_number + offset
        filename = task_filename(number, spec["title"])
        child_tasks.append({"filename": filename, "title": spec["title"], "goal": spec["goal"]})

    recommended_start = child_tasks[0]["filename"]
    child_lines = [f"- `{item['filename']}`: {item['goal']}" for item in child_tasks]
    order_lines = [f"{index}. `{item['filename']}`" for index, item in enumerate(child_tasks, start=1)]
    risk_lines: list[str] = []
    if intake.get("warnings"):
        risk_lines.extend([f"- Review initialization warning before starting child work: {warning}" for warning in intake.get("warnings", [])[:3]])
    if intake.get("conflicts"):
        risk_lines.append(f"- Review recorded source conflicts from `.repo-init/init-report.md` before starting `{recommended_start}`.")
    if not risk_lines:
        risk_lines.append("- No blocking cross-task risks were identified during initialization.")

    master_content = build_task_document(
        title=master_title,
        filename=master_filename,
        why=master_why,
        in_scope=["coordinate the first-wave task set", "keep child-task ordering and dependencies explicit"],
        out_of_scope=["executing child tasks during initialization", "deep second-level task decomposition"],
        acceptance=[
            "Execution feedback can be reviewed in one coordination surface.",
            "Affected tasks and suggested replan actions remain visible.",
            "Suggested replan actions stay separate from accepted replan decisions.",
        ],
        files_dep=["PROJECT.md", "STATUS.md", source_ref],
        decisions_dep=[],
        external_dep=[],
        plan=[
            "Review the generated child task set and confirm the proposed starting sequence.",
            "Consolidate cross-task feedback in this task before changing downstream work.",
            "Promote only explicitly accepted adjustments into `Replan Decisions` before revising task order or definitions.",
        ],
        facts=[
            f"complexity level is `{complexity.get('level', 'simple')}`",
            f"complexity score is `{complexity.get('score', 0)}`",
            f"decomposition was auto-applied because `{decomposition.get('reason', 'complex project signals were detected')}`",
        ],
        assumptions=[f"complexity signals are `{', '.join(complexity.get('signals') or ['none'])}`"],
        risks=["task order may still need reprioritization once explicit execution begins"],
        assumption_still_open=["The initial child-task order remains provisional until real execution feedback arrives."],
        downstream_follow_up=[
            "When a child task changes ordering, blockers, or acceptance expectations, update `STATUS.md` and this task before changing downstream work.",
            "Only move accepted reorder or scope changes into `Replan Decisions` before rewriting child tasks.",
        ],
        extra_sections=[
            ("Child Tasks", child_lines),
            ("Recommended Order", order_lines),
            (
                "Replan Triggers",
                [
                    "- blocker introduced or removed",
                    "- acceptance failed or changed",
                    "- assumption invalidated",
                    "- new dependency found",
                    "- scope clarification received",
                ],
            ),
            (
                "Feedback Ledger",
                [
                    "- No execution feedback recorded yet.",
                    "- Use: `Date=<YYYY-MM-DD>; Source Task=<task-id>; Observation=<high-signal feedback>; Impacted Tasks=<task-id or none>; Suggested Action=<keep|reorder|block|split|revise-acceptance|clarify>`",
                ],
            ),
            (
                "Replan Decisions",
                [
                    "- none accepted yet",
                    "- Record only explicitly accepted task-order or task-definition changes here.",
                ],
            ),
            ("Hold Rules", ["- Do not start child tasks automatically during initialization.", f"- Explicitly confirm `{recommended_start}` before beginning execution."]),
            ("Cross-Task Risks", risk_lines),
        ],
    )

    rendered: list[tuple[str, str]] = [(master_filename, master_content)]
    parent_id = task_id_from_filename(master_filename)
    child_filenames: list[str] = []
    for index, item in enumerate(child_tasks, start=1):
        related = []
        if index > 1:
            related.append(f"- Review `{child_tasks[index - 2]['filename']}` for upstream context before execution.")
        if index < len(child_tasks):
            related.append(f"- Coordinate boundaries with `{child_tasks[index]['filename']}` before handoff.")
        if not related:
            related.append("- No adjacent child-task dependency was inferred during initialization.")

        child_content = build_task_document(
            title=item["title"],
            filename=item["filename"],
            why=item["goal"],
            in_scope=[item["goal"]],
            out_of_scope=["cross-task coordination beyond this slice", "starting unrelated implementation slices"],
            acceptance=[
                "This slice has a clear, single execution target aligned with `PROJECT.md`.",
                "Dependencies and boundaries with adjacent tasks are explicit.",
                "Validation expectations for this slice are clear before execution begins.",
            ],
            files_dep=["PROJECT.md", "STATUS.md", source_ref],
            decisions_dep=[parent_id],
            external_dep=[],
            plan=[
                f"Review the project snapshot and constraints for `{item['title']}`.",
                f"Prepare the concrete implementation approach for `{item['title']}`.",
                f"Execute and validate `{item['title']}` once this slice is explicitly started.",
            ],
            facts=[f"parent task is `{master_filename}`", f"recommended order position is `{index}`"],
            assumptions=["this slice remains `todo` until a human or agent explicitly starts it"],
            risks=["coordination with adjacent task slices may still require reprioritization"],
            assumption_still_open=["Execution feedback from this slice may still change adjacent-task ordering or boundaries."],
            downstream_follow_up=[
                f"If this slice affects other work, update `{master_filename}` `Feedback Ledger` and `STATUS.md` before changing downstream tasks.",
            ],
            extra_sections=[
                ("Parent Coordination", [f"- Parent task: `{master_filename}`", "- Start this task only after explicit post-initialization confirmation."]),
                ("Related Tasks", related),
            ],
            parent_id=parent_id,
        )
        rendered.append((item["filename"], child_content))
        child_filenames.append(item["filename"])

    return {
        "files": rendered,
        "active_task": master_filename,
        "recommended_start_task": recommended_start,
        "master_task": master_filename,
        "child_tasks": child_filenames,
        "decomposition_applied": True,
    }


def render_task_set(
    repo_root: Path,
    mode: str,
    intake: dict[str, Any],
    repo_summary: dict[str, Any],
    summary: dict[str, Any],
) -> TaskPlan:
    """Render either a single task or a decomposed task set."""
    decomposition = intake.get("task_decomposition") or {}
    if decomposition.get("applied"):
        return render_decomposed_task_set(repo_root, mode, intake, repo_summary, summary)
    return render_simple_task_set(repo_root, mode, intake)
