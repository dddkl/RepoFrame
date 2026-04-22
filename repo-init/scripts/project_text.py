#!/usr/bin/env python3
"""Low-level text parsing helpers shared by repo-init scripts."""

from __future__ import annotations

import re

from repo_init_common import normalize_text, unique


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
    match = re.search(rf"(?:{'|'.join(patterns)})\s*[:\uFF1A]\s*(.+?)(?:$|\n)", text, re.IGNORECASE)
    return normalize_text(match.group(1)) if match else ""


def split_list_items(text: str) -> list[str]:
    """Split free-form list text into items."""
    raw = text.replace("\n", ", ")
    raw = raw.replace(" and ", ", ")
    items = [item.strip(" -") for item in raw.split(",")]
    return unique([item for item in items if item])


def extract_use_stack(text: str) -> list[str]:
    """Extract a stack list from free-form prompt text."""
    match = re.search(r"\buse\s+(.+?)(?=\s+do not\b|\s+stage(?:\s+is|[:\uFF1A])|\s+users?\s*[:\uFF1A]|\n|$)", text, re.IGNORECASE)
    if not match:
        return []
    stack_text = match.group(1).strip().rstrip(".")
    return split_list_items(stack_text)
