"""Deterministic Git mutations used by RepoFrame interactive operations."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
from pathlib import Path
from typing import Any

from .git_inspect import GitInspectionError, inspect_repository


class GitOperationError(RuntimeError):
    """Raised when a fixed RepoFrame Git operation cannot complete."""

    def __init__(self, message: str, *, code: str = "git_failed", details: str = "") -> None:
        super().__init__(message)
        self.code = code
        self.details = details


def _environment() -> dict[str, str]:
    environment = os.environ.copy()
    environment["GIT_TERMINAL_PROMPT"] = "0"
    return environment


def _run(
    repo: Path,
    *arguments: str,
    input_bytes: bytes | None = None,
    timeout: int = 60,
    allow_failure: bool = False,
) -> subprocess.CompletedProcess[bytes]:
    try:
        result = subprocess.run(
            ["git", "-C", str(repo), *arguments],
            input=input_bytes,
            check=False,
            capture_output=True,
            env=_environment(),
            timeout=timeout,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise GitOperationError(f"Unable to run Git: {exc}") from exc
    if result.returncode and not allow_failure:
        details = result.stderr.decode("utf-8", "replace").strip()
        raise GitOperationError(details or "Git command failed.", details=details)
    return result


def _untracked_metadata(repo: Path, files: list[dict[str, Any]]) -> list[tuple[str, int, int]]:
    metadata: list[tuple[str, int, int]] = []
    root = repo.resolve()
    for item in files:
        if item.get("status") != "untracked":
            continue
        relative = Path(str(item["path"]))
        candidate = (root / relative).resolve(strict=False)
        if not candidate.is_relative_to(root):
            continue
        try:
            stat = candidate.stat()
        except OSError:
            metadata.append((relative.as_posix(), -1, -1))
            continue
        metadata.append((relative.as_posix(), stat.st_size, stat.st_mtime_ns))
    return metadata


def working_tree_snapshot(repo: Path) -> dict[str, Any]:
    """Return Git facts plus a fingerprint used to reject stale proposals."""
    try:
        inspection = inspect_repository(repo)
    except GitInspectionError as exc:
        raise GitOperationError(str(exc), code="git_unavailable") from exc
    status = _run(repo, "status", "--porcelain=v1", "-z", "--untracked-files=all").stdout
    unstaged = _run(repo, "diff", "--no-ext-diff", "--no-textconv", "--binary").stdout
    staged = _run(repo, "diff", "--cached", "--no-ext-diff", "--no-textconv", "--binary").stdout
    untracked = _untracked_metadata(repo, inspection["working_changes"]["files"])
    digest = hashlib.sha256()
    for chunk in (status, unstaged, staged, json.dumps(untracked, separators=(",", ":")).encode("utf-8")):
        digest.update(len(chunk).to_bytes(8, "big"))
        digest.update(chunk)
    return {"fingerprint": digest.hexdigest(), "inspection": inspection}


def commit_all(repo: Path, fingerprint: str, subject: str, body: str = "") -> dict[str, Any]:
    """Stage every working-tree change and create one commit."""
    current = working_tree_snapshot(repo)
    changes = current["inspection"]["working_changes"]
    if not changes["changed_files"]:
        raise GitOperationError("The working tree has no changes to commit.", code="no_changes")
    if current["fingerprint"] != fingerprint:
        raise GitOperationError(
            "The working tree changed after the proposal was generated.",
            code="proposal_stale",
        )
    clean_subject = subject.strip()
    if not clean_subject or "\n" in clean_subject or "\r" in clean_subject:
        raise GitOperationError("Commit subject must be one non-empty line.", code="invalid_message")
    if len(clean_subject) > 120:
        raise GitOperationError("Commit subject must not exceed 120 characters.", code="invalid_message")
    message = clean_subject
    clean_body = body.strip()
    if clean_body:
        message += f"\n\n{clean_body}"

    _run(repo, "add", "-A")
    staged = _run(repo, "diff", "--cached", "--quiet", allow_failure=True)
    if staged.returncode == 0:
        raise GitOperationError("There are no staged changes to commit.", code="no_changes")
    if staged.returncode not in {0, 1}:
        details = staged.stderr.decode("utf-8", "replace").strip()
        raise GitOperationError(details or "Unable to inspect staged changes.", details=details)
    _run(repo, "commit", "-F", "-", input_bytes=(message + "\n").encode("utf-8"), timeout=180)
    commit_hash = _run(repo, "rev-parse", "HEAD").stdout.decode("ascii", "replace").strip()
    short_hash = _run(repo, "rev-parse", "--short", "HEAD").stdout.decode("ascii", "replace").strip()
    return {"hash": commit_hash, "short_hash": short_hash, "subject": clean_subject}


def push_current(repo: Path) -> dict[str, Any]:
    """Push the current branch without changing upstream or using force."""
    result = _run(repo, "push", timeout=180, allow_failure=True)
    if result.returncode:
        details = result.stderr.decode("utf-8", "replace").strip()
        raise GitOperationError(
            details or "Git push failed; the local commit is preserved.",
            code="push_failed",
            details=details,
        )
    return {"pushed": True}
