#!/usr/bin/env python3
"""Repository output helpers for repo initialization."""

from __future__ import annotations

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


def append_if_missing(path: Path, section_title: str, section_body: str) -> None:
    """Append a section to a populated file if it is not already present."""
    existing = path.read_text(encoding="utf-8", errors="replace")
    if section_title in existing:
        return
    updated = existing.rstrip() + "\n\n" + section_body.strip() + "\n"
    path.write_text(updated, encoding="utf-8")


def apply_outputs(repo_root: Path, policy_json: dict, content_map: dict[str, str], task_plan: TaskPlan) -> FileChanges:
    """Write repository outputs according to the computed policy."""
    tasks_dir = repo_root / "tasks"
    tasks_dir_preexisted = tasks_dir.exists()
    tasks_dir.mkdir(parents=True, exist_ok=True)

    created: list[str] = []
    supplemented: list[str] = []
    preserved: list[str] = []

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

    for filename, task_content in task_plan["files"]:
        task_path = tasks_dir / filename
        if task_path.exists():
            supplemented.append(f"tasks/{filename}")
        else:
            created.append(f"tasks/{filename}")
        task_path.write_text(task_content, encoding="utf-8")

    if not tasks_dir_preexisted:
        created.append("tasks/")
    else:
        supplemented.append("tasks/")

    return {
        "created": unique(created),
        "supplemented": unique(supplemented),
        "preserved": unique(preserved),
    }
