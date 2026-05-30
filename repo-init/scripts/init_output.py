#!/usr/bin/env python3
"""Repository output helpers for repo initialization."""

from __future__ import annotations

import re
import json
from pathlib import Path
from typing import TypedDict

from init_task_plan import TaskPlan
from repo_init_common import MANAGED_MARKER, unique


TARGET_FILES = ("README.md", "AGENT.md", "PROJECT.md", "STATUS.md", "DECISIONS.md")


class FileChanges(TypedDict):
    """Grouped file-change summary for initialization output."""

    created: list[str]
    supplemented: list[str]
    preserved: list[str]


def write_managed_file(path: Path, content: str) -> None:
    """Write a managed file."""
    path.write_text(content, encoding="utf-8")


def is_managed_acceptance_json(path: Path) -> bool:
    """Return True when an acceptance file is managed by RepoFrame."""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    return payload.get("managed_by") == "RepoFrame"


def upsert_markdown_section(path: Path, section_title: str, section_body: str) -> None:
    """Append or replace a top-level markdown section in a populated file."""
    existing = path.read_text(encoding="utf-8", errors="replace")
    replacement = section_body.strip() + "\n\n"
    pattern = rf"(?ms)^{re.escape(section_title)}\n.*?(?=^##\s|\Z)"
    if re.search(pattern, existing):
        updated = re.sub(pattern, replacement, existing, count=1)
    else:
        updated = existing.rstrip() + "\n\n" + section_body.strip() + "\n"
    path.write_text(updated.rstrip() + "\n", encoding="utf-8")


def apply_outputs(
    repo_root: Path,
    policy_json: dict,
    content_map: dict[str, str],
    task_plan: TaskPlan,
    readme_supplement: str,
    agent_docs: dict[str, str] | None = None,
    acceptance_content: str | None = None,
) -> FileChanges:
    """Write repository outputs according to the computed policy."""
    tasks_dir = repo_root / "tasks"
    goals_dir = repo_root / "goals"
    agent_docs_dir = repo_root / ".agent"
    tasks_dir_preexisted = tasks_dir.exists()
    goals_dir_preexisted = goals_dir.exists()
    agent_docs_dir_preexisted = agent_docs_dir.exists()
    tasks_dir.mkdir(parents=True, exist_ok=True)
    goals_dir.mkdir(parents=True, exist_ok=True)
    agent_docs_dir.mkdir(parents=True, exist_ok=True)

    created: list[str] = []
    supplemented: list[str] = []
    preserved: list[str] = []

    for target in TARGET_FILES:
        path = repo_root / target
        policy = policy_json["files"][target]["policy"]
        state = policy_json["files"][target]["state"]
        existing_text = path.read_text(encoding="utf-8", errors="replace") if path.exists() else ""

        if target == "PROJECT.md" and policy == "preserve":
            preserved.append(target)
            continue

        if policy == "create" or state in {"missing", "empty", "template"}:
            write_managed_file(path, content_map[target])
            created.append(target)
            continue

        if existing_text and MANAGED_MARKER in existing_text:
            write_managed_file(path, content_map[target])
            supplemented.append(target)
            continue

        if target == "README.md":
            upsert_markdown_section(path, "## Collaboration Layer", readme_supplement)
            supplemented.append(target)
            continue

        preserved.append(target)

    if acceptance_content is not None:
        acceptance_path = repo_root / "acceptance.json"
        policy = policy_json["files"].get("acceptance.json", {}).get("policy", "create")
        state = policy_json["files"].get("acceptance.json", {}).get("state", "missing")
        if policy == "create" or state in {"missing", "empty", "template"}:
            write_managed_file(acceptance_path, acceptance_content)
            created.append("acceptance.json")
        elif acceptance_path.exists() and is_managed_acceptance_json(acceptance_path):
            write_managed_file(acceptance_path, acceptance_content)
            supplemented.append("acceptance.json")
        else:
            preserved.append("acceptance.json")

    for filename, goal_content in task_plan["goal_files"]:
        goal_path = goals_dir / filename
        if goal_path.exists():
            supplemented.append(f"goals/{filename}")
        else:
            created.append(f"goals/{filename}")
        goal_path.write_text(goal_content, encoding="utf-8")

    for filename, task_content in task_plan["files"]:
        task_path = tasks_dir / filename
        if task_path.exists():
            supplemented.append(f"tasks/{filename}")
        else:
            created.append(f"tasks/{filename}")
        task_path.write_text(task_content, encoding="utf-8")

    for relative_path, doc_content in (agent_docs or {}).items():
        doc_path = repo_root / relative_path
        existing_text = doc_path.read_text(encoding="utf-8", errors="replace") if doc_path.exists() else ""
        if not doc_path.exists():
            created.append(relative_path)
            doc_path.write_text(doc_content, encoding="utf-8")
            continue
        if not existing_text.strip() or MANAGED_MARKER in existing_text:
            supplemented.append(relative_path)
            doc_path.write_text(doc_content, encoding="utf-8")
            continue
        preserved.append(relative_path)

    if not goals_dir_preexisted:
        created.append("goals/")
    else:
        supplemented.append("goals/")

    if not tasks_dir_preexisted:
        created.append("tasks/")
    else:
        supplemented.append("tasks/")

    if not agent_docs_dir_preexisted:
        created.append(".agent/")
    else:
        supplemented.append(".agent/")

    return {
        "created": unique(created),
        "supplemented": unique(supplemented),
        "preserved": unique(preserved),
    }
