"""Read iteration activity directly from Git without creating RepoFrame state."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Any


class GitInspectionError(RuntimeError):
    """Raised when a repository cannot be inspected safely."""


def _run(repo: Path, *arguments: str, allow_failure: bool = False) -> bytes:
    environment = os.environ.copy()
    environment["GIT_OPTIONAL_LOCKS"] = "0"
    environment["GIT_TERMINAL_PROMPT"] = "0"
    try:
        result = subprocess.run(
            ["git", "-C", str(repo), *arguments],
            check=False,
            capture_output=True,
            env=environment,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise GitInspectionError(f"Unable to run Git: {exc}") from exc
    if result.returncode and not allow_failure:
        message = result.stderr.decode("utf-8", "replace").strip() or "Git command failed."
        raise GitInspectionError(message)
    return result.stdout


def _diff_totals(raw: bytes) -> tuple[int, int]:
    additions = 0
    deletions = 0
    for line in raw.decode("utf-8", "replace").splitlines():
        parts = line.split("\t", 2)
        if len(parts) < 2:
            continue
        if parts[0].isdigit():
            additions += int(parts[0])
        if parts[1].isdigit():
            deletions += int(parts[1])
    return additions, deletions


def _status_name(index: str, worktree: str) -> str:
    codes = f"{index}{worktree}"
    if "?" in codes:
        return "untracked"
    if "U" in codes or codes in {"AA", "DD"}:
        return "conflicted"
    if "R" in codes:
        return "renamed"
    if "C" in codes:
        return "copied"
    if "D" in codes:
        return "deleted"
    if "A" in codes:
        return "added"
    return "modified"


def _working_files(raw: bytes) -> list[dict[str, Any]]:
    records = raw.decode("utf-8", "replace").split("\0")
    files: list[dict[str, Any]] = []
    index = 0
    while index < len(records):
        record = records[index]
        index += 1
        if not record or len(record) < 3:
            continue
        index_status, worktree_status = record[0], record[1]
        path = record[3:]
        original_path: str | None = None
        if index_status in {"R", "C"} or worktree_status in {"R", "C"}:
            if index < len(records) and records[index]:
                original_path = records[index]
                index += 1
        item: dict[str, Any] = {
            "path": path,
            "status": _status_name(index_status, worktree_status),
            "staged": index_status not in {" ", "?"},
            "unstaged": worktree_status not in {" ", "?"},
        }
        if original_path is not None:
            item["original_path"] = original_path
        files.append(item)
    return files


def _commits(raw: bytes) -> list[dict[str, str]]:
    commits: list[dict[str, str]] = []
    for record in raw.decode("utf-8", "replace").split("\x1e"):
        record = record.strip("\r\n")
        if not record:
            continue
        fields = record.split("\x1f", 4)
        if len(fields) != 5:
            continue
        commit_hash, short_hash, author, authored_at, subject = fields
        commits.append(
            {
                "hash": commit_hash,
                "short_hash": short_hash,
                "author": author,
                "authored_at": authored_at,
                "subject": subject,
            }
        )
    return commits


def inspect_repository(repo: Path, *, commit_limit: int = 12) -> dict[str, Any]:
    """Return a compact, JSON-serializable snapshot of repository activity."""
    repo = repo.resolve()
    inside = _run(repo, "rev-parse", "--is-inside-work-tree", allow_failure=True).strip()
    if inside != b"true":
        raise GitInspectionError("The viewer directory is not inside a Git working tree.")

    status_raw = _run(repo, "status", "--porcelain=v1", "-z", "--untracked-files=all")
    files = _working_files(status_raw)
    diff_options = ("--no-ext-diff", "--no-textconv", "--numstat")
    unstaged_additions, unstaged_deletions = _diff_totals(_run(repo, "diff", *diff_options))
    staged_additions, staged_deletions = _diff_totals(_run(repo, "diff", "--cached", *diff_options))

    branch = _run(repo, "symbolic-ref", "--short", "-q", "HEAD", allow_failure=True).decode(
        "utf-8", "replace"
    ).strip()
    if not branch:
        detached = _run(repo, "rev-parse", "--short", "HEAD", allow_failure=True).decode(
            "utf-8", "replace"
        ).strip()
        branch = f"detached@{detached}" if detached else "unborn"

    log_raw = _run(
        repo,
        "log",
        f"-n{max(1, commit_limit)}",
        "--format=%H%x1f%h%x1f%an%x1f%aI%x1f%s%x1e",
        allow_failure=True,
    )
    commits = _commits(log_raw)
    return {
        "repository": repo.name,
        "branch": branch,
        "clean": not files,
        "working_changes": {
            "changed_files": len(files),
            "staged_files": sum(1 for item in files if item["staged"]),
            "unstaged_files": sum(1 for item in files if item["unstaged"]),
            "untracked_files": sum(1 for item in files if item["status"] == "untracked"),
            "additions": staged_additions + unstaged_additions,
            "deletions": staged_deletions + unstaged_deletions,
            "files": files,
        },
        "latest_commit": commits[0] if commits else None,
        "recent_commits": commits,
    }
