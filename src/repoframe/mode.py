"""Repository-local RepoFrame mode and provider configuration."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path


MODES = {"iteration", "long-run"}
PROVIDERS = {"codex", "claude", "gemini"}


class ModeError(RuntimeError):
    """Raised when repository-local RepoFrame configuration is unavailable."""


def _git(repo: Path, *arguments: str, timeout: int = 10) -> subprocess.CompletedProcess[bytes]:
    environment = os.environ.copy()
    environment["GIT_TERMINAL_PROMPT"] = "0"
    try:
        return subprocess.run(
            ["git", "-C", str(repo), *arguments],
            check=False,
            capture_output=True,
            env=environment,
            timeout=timeout,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ModeError(f"Unable to run Git: {exc}") from exc


def is_git_repository(repo: Path) -> bool:
    """Return whether repo is inside a Git working tree."""
    result = _git(repo, "rev-parse", "--is-inside-work-tree")
    return result.returncode == 0 and result.stdout.strip() == b"true"


def get_mode(repo: Path) -> str:
    """Read the repository-local mode or infer the least surprising default."""
    if is_git_repository(repo):
        result = _git(repo, "config", "--local", "--get", "repoframe.mode")
        value = result.stdout.decode("utf-8", "replace").strip()
        if result.returncode == 0 and value in MODES:
            return value
    return "long-run" if (repo / ".repoframe/state.json").exists() else "iteration"


def set_mode(repo: Path, mode: str) -> None:
    """Persist mode in local Git configuration without dirtying the worktree."""
    if mode not in MODES:
        raise ModeError(f"Unknown RepoFrame mode: {mode}")
    if not is_git_repository(repo):
        raise ModeError("Iteration and interactive mode require a Git working tree.")
    result = _git(repo, "config", "--local", "repoframe.mode", mode)
    if result.returncode:
        message = result.stderr.decode("utf-8", "replace").strip() or "Unable to update Git configuration."
        raise ModeError(message)


def get_provider(repo: Path) -> str:
    """Return the configured operation Agent provider."""
    if is_git_repository(repo):
        result = _git(repo, "config", "--local", "--get", "repoframe.agent-provider")
        value = result.stdout.decode("utf-8", "replace").strip().lower()
        if result.returncode == 0 and value:
            return value
    return "codex"


def initialize_mode(repo: Path, mode: str) -> None:
    """Set the initial mode when initialization runs in a Git repository."""
    if is_git_repository(repo):
        set_mode(repo, mode)
