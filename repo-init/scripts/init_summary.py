#!/usr/bin/env python3
"""Project summary and clarification helpers for repo initialization."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from project_text import extract_use_stack, find_labeled_value, find_section, split_list_items
from repo_init_common import normalize_text, unique


def infer_project_name(title: str, text: str, repo_root: Path) -> str:
    """Infer a project name."""
    patterns = [
        r"\bcalled\s+([A-Z][A-Za-z0-9_-]+)",
        r"\bnamed\s+([A-Z][A-Za-z0-9_-]+)",
        r"^\s*project\s*[:\uFF1A]\s*([A-Za-z0-9 _-]+)$",
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


def infer_greenfield_fields(intake: dict[str, Any], repo_root: Path) -> dict[str, Any]:
    """Infer structured fields from prompt input."""
    text = intake.get("extracted_text", "")
    name = infer_project_name(intake.get("title") or "", text, repo_root)
    goal = find_labeled_value(text, ["goal", "objective", "purpose"])
    project_type_match = re.search(r"initialize this repository as (?:an?|the)\s+(.+?)(?:\s+called|\s+named|\.|,|\n)", text, re.IGNORECASE)
    project_type = project_type_match.group(1).strip() if project_type_match else "project"
    stage = find_labeled_value(text, ["stage"]).lower()
    stack = extract_use_stack(text)
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


def infer_plan_snapshot(intake: dict[str, Any], repo_root: Path) -> dict[str, Any]:
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
        "stack": split_list_items(stack) if stack else [],
        "constraints": unique([line.strip("- ") for line in constraints.splitlines() if line.strip()]) if constraints else [],
        "assumptions": [
            "The provided source document remains the authoritative project definition unless the user asks for a rewrite.",
        ],
    }


def merged_summary(intake: dict[str, Any], repo_root: Path, mode: str) -> dict[str, Any]:
    """Build a project summary from bundle intake with backwards-compatible fallbacks."""
    base: dict[str, Any] = {
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

    base["assumptions"] = unique(
        [*(fallback.get("assumptions") or []), *(merged.get("assumptions") or []), *(base.get("assumptions") or [])]
    )
    return base


def low_confidence(intake: dict[str, Any]) -> bool:
    """Return True when intake should be handled conservatively."""
    confidence = intake.get("bundle_confidence", intake.get("confidence", 0))
    return confidence < 0.5 or not intake.get("extracted_text", "").strip()


def needs_clarification(intake: dict[str, Any]) -> bool:
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
        "stack": split_list_items(stack) if stack else [],
    }


def canonical_field_value(value: str | list[str]) -> str:
    """Canonicalize values for comparison."""
    if isinstance(value, list):
        normalized = [normalize_text(item).lower() for item in value if normalize_text(item)]
        return " | ".join(sorted(unique(normalized)))
    return normalize_text(str(value or "")).lower()


def detect_repo_hydrate_clarifications(repo_root: Path, intake: dict[str, Any]) -> tuple[list[str], list[str]]:
    """Detect repo-hydrate conflicts between bundle input and existing repository docs."""
    if intake.get("source_type") == "prompt" and not intake.get("source_count", 0):
        return [], []

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


def source_reference(intake: dict[str, Any]) -> str:
    """Return a readable source reference."""
    roles = intake.get("source_roles") or []
    if roles:
        return ", ".join(item["label"] for item in roles)
    return intake.get("source_path") or "prompt-only input"
