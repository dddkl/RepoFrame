#!/usr/bin/env python3
"""Shared helpers for repo-init skill scripts."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

VERSION = "0.1.0"
DEFAULT_ARTIFACT_DIRNAME = ".repo-init"
MANAGED_MARKER = "<!-- repo-init:managed -->"

IGNORE_DIRS = {
    ".git",
    ".hg",
    ".svn",
    ".idea",
    ".vscode",
    "__pycache__",
    "node_modules",
    "dist",
    "build",
    "coverage",
    ".next",
    ".repo-init",
    ".venv",
    ".tmp",
    "_repo_init_tmp",
    "venv",
    ".mypy_cache",
    ".pytest_cache",
    "tmp",
}

CODE_SUFFIXES = {
    ".c",
    ".cc",
    ".cpp",
    ".cs",
    ".go",
    ".h",
    ".hpp",
    ".java",
    ".js",
    ".jsx",
    ".kt",
    ".mjs",
    ".php",
    ".ps1",
    ".py",
    ".rb",
    ".rs",
    ".sh",
    ".sql",
    ".swift",
    ".ts",
    ".tsx",
    ".yaml",
    ".yml",
}

MANIFEST_NAMES = {
    "Cargo.toml",
    "Makefile",
    "package.json",
    "pnpm-lock.yaml",
    "pom.xml",
    "pyproject.toml",
    "requirements.txt",
    "tsconfig.json",
}

TARGET_DOCS = (
    "README.md",
    "AGENT.md",
    "PROJECT.md",
    "STATUS.md",
    "DECISIONS.md",
    "acceptance.json",
)

PLACEHOLDER_RE = re.compile(r"<[^>\n]{1,80}>")


def utc_now_iso() -> str:
    """Return a compact UTC timestamp."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def unique(items: list[str]) -> list[str]:
    """Preserve order while removing duplicates."""
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            result.append(item)
    return result


def normalize_text(text: str) -> str:
    """Normalize whitespace while preserving paragraphs."""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = [line.rstrip() for line in text.split("\n")]
    text = "\n".join(lines)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def first_non_empty_line(text: str) -> str:
    """Return the first non-empty line or an empty string."""
    for line in text.splitlines():
        line = line.strip()
        if line:
            return line
    return ""


def read_text_with_fallback(path: Path) -> tuple[str, list[str]]:
    """Read text from a file with simple encoding fallbacks."""
    warnings: list[str] = []
    for encoding in ("utf-8", "utf-8-sig", "cp1252", "latin-1"):
        try:
            return path.read_text(encoding=encoding), warnings
        except UnicodeDecodeError:
            warnings.append(f"Failed to decode {path.name} as {encoding}.")
    return path.read_text(encoding="utf-8", errors="replace"), warnings + [
        f"Used replacement decoding for {path.name}.",
    ]


def write_json(data: dict[str, Any], output_path: str | None) -> None:
    """Write JSON to a file or stdout."""
    text = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
    if output_path:
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return
    print(text, end="")


def write_text(text: str, output_path: str | None) -> str | None:
    """Write text to a file and return the resolved path."""
    if not output_path:
        return None
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return str(path.resolve())


def load_json(path: str) -> dict[str, Any]:
    """Load a JSON file."""
    return json.loads(Path(path).read_text(encoding="utf-8"))


def classify_text_state(path: Path) -> str:
    """Classify an existing markdown-like file."""
    if not path.exists():
        return "missing"
    text = normalize_text(path.read_text(encoding="utf-8", errors="replace"))
    if not text:
        return "empty"
    if text.count("TODO") >= 2 or len(PLACEHOLDER_RE.findall(text)) >= 2:
        return "template"
    return "populated"


def iter_repo_files(repo_root: Path) -> list[Path]:
    """List meaningful files under a repository root."""
    files: list[Path] = []
    for path in repo_root.rglob("*"):
        if not path.is_file():
            continue
        parts = set(path.relative_to(repo_root).parts[:-1])
        if parts & IGNORE_DIRS:
            continue
        files.append(path)
    return sorted(files)


def summarize_repo(repo_root: Path) -> dict[str, Any]:
    """Summarize repository contents for mode classification."""
    files = iter_repo_files(repo_root)
    relative_files = [path.relative_to(repo_root).as_posix() for path in files]
    code_files = [
        rel
        for rel, path in zip(relative_files, files)
        if path.suffix.lower() in CODE_SUFFIXES or path.name in MANIFEST_NAMES
    ]
    doc_files = [
        rel
        for rel in relative_files
        if rel in TARGET_DOCS or rel.startswith("goals/") or rel.startswith("tasks/") or rel.startswith(".agent/")
    ]
    return {
        "meaningful_file_count": len(relative_files),
        "code_file_count": len(code_files),
        "partial_doc_count": len(doc_files),
        "sample_files": relative_files[:12],
    }


def clamp(value: float, lower: float, upper: float) -> float:
    """Clamp a float into a range."""
    return max(lower, min(upper, value))


def slugify(text: str, default: str = "item") -> str:
    """Convert free text into a stable slug."""
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    text = text.strip("-")
    return text or default
