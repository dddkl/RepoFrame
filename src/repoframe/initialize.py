"""Initialize RepoFrame state and thin agent instruction adapters."""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass
from importlib import resources
from pathlib import Path

from .state import load_and_validate, new_state, validate_state


START_MARKER = "<!-- repoframe:start -->"
END_MARKER = "<!-- repoframe:end -->"
MANAGED_BLOCK = """<!-- repoframe:start -->
## RepoFrame

Before starting or resuming multi-step work, read
`.repoframe/state.json` and `.repoframe/instructions.md`.

Keep the RepoFrame DAG aligned with meaningful execution-state changes.
Run `repoframe validate` after updating it.
<!-- repoframe:end -->
"""
AGENT_PATHS = {
    "codex": Path("AGENTS.md"),
    "cursor": Path("AGENTS.md"),
    "claude": Path("CLAUDE.md"),
    "gemini": Path("GEMINI.md"),
    "copilot": Path(".github/copilot-instructions.md"),
}


class InitializationError(RuntimeError):
    """Raised when initialization cannot proceed without unsafe writes."""


@dataclass(frozen=True)
class Change:
    path: Path
    action: str


def _resource_text(name: str) -> str:
    return resources.files("repoframe.resources").joinpath(name).read_text(encoding="utf-8")


def _selected_adapter_paths(repo: Path, selection: str) -> list[Path]:
    normalized = selection.strip().lower()
    if normalized == "none":
        return []
    if normalized == "all":
        agents = list(AGENT_PATHS)
    elif normalized == "auto":
        agents = [name for name, path in AGENT_PATHS.items() if (repo / path).exists()]
        if not agents:
            agents = ["codex"]
    else:
        agents = [part.strip() for part in normalized.split(",") if part.strip()]
        unknown = sorted(set(agents) - set(AGENT_PATHS))
        if unknown:
            raise InitializationError(f"Unknown agent selection: {', '.join(unknown)}")
        if not agents:
            raise InitializationError("Agent selection cannot be empty.")
    paths: list[Path] = []
    for agent in agents:
        path = AGENT_PATHS[agent]
        if path not in paths:
            paths.append(path)
    return paths


def _managed_text(existing: str, path: Path) -> str:
    starts = existing.count(START_MARKER)
    ends = existing.count(END_MARKER)
    if starts != ends or starts > 1:
        raise InitializationError(f"Invalid RepoFrame managed markers in {path}.")
    if starts == 0:
        separator = "" if not existing else ("\n" if existing.endswith("\n") else "\n\n")
        return f"{existing}{separator}{MANAGED_BLOCK}"
    start = existing.index(START_MARKER)
    end_start = existing.find(END_MARKER, start + len(START_MARKER))
    if end_start < 0:
        raise InitializationError(f"Invalid RepoFrame managed markers in {path}.")
    end = end_start + len(END_MARKER)
    suffix = existing[end:]
    if suffix.startswith("\r\n"):
        suffix = suffix[2:]
    elif suffix.startswith("\n"):
        suffix = suffix[1:]
    return f"{existing[:start]}{MANAGED_BLOCK}{suffix}"


def _safe_target(repo: Path, relative: Path) -> Path:
    if relative.is_absolute() or ".." in relative.parts:
        raise InitializationError(f"Managed path is not repository-relative: {relative}")
    target = repo / relative
    resolved = target.resolve(strict=False)
    if not resolved.is_relative_to(repo):
        raise InitializationError(f"Managed path resolves outside the repository: {relative}")
    return target


def _write_batch(repo: Path, planned: dict[Path, bytes]) -> None:
    staged: dict[Path, Path] = {}
    originals: dict[Path, bytes | None] = {}
    applied: list[Path] = []
    try:
        for relative, content in planned.items():
            target = _safe_target(repo, relative)
            target.parent.mkdir(parents=True, exist_ok=True)
            target = _safe_target(repo, relative)
            originals[relative] = target.read_bytes() if target.exists() else None
            handle, temporary = tempfile.mkstemp(prefix=f".{target.name}.", suffix=".tmp", dir=target.parent)
            with os.fdopen(handle, "wb") as stream:
                stream.write(content)
                stream.flush()
                os.fsync(stream.fileno())
            staged[relative] = Path(temporary)
        for relative, temporary in staged.items():
            os.replace(temporary, repo / relative)
            applied.append(relative)
    except OSError as exc:
        for relative in reversed(applied):
            target = repo / relative
            original = originals[relative]
            if original is None:
                target.unlink(missing_ok=True)
            else:
                handle, temporary = tempfile.mkstemp(prefix=f".{target.name}.rollback.", dir=target.parent)
                with os.fdopen(handle, "wb") as stream:
                    stream.write(original)
                os.replace(temporary, target)
        raise InitializationError(f"Unable to write RepoFrame files atomically: {exc}") from exc
    finally:
        for temporary in staged.values():
            temporary.unlink(missing_ok=True)


def initialize(
    repo: Path,
    goal: str | None,
    outcome: str | None,
    criteria: list[str],
    constraints: list[str],
    agents: str = "auto",
) -> list[Change]:
    """Plan and atomically apply RepoFrame initialization."""
    repo = repo.resolve()
    if not repo.exists() or not repo.is_dir():
        raise InitializationError(f"Repository directory does not exist: {repo}")
    adapter_paths = _selected_adapter_paths(repo, agents)
    state_relative = Path(".repoframe/state.json")
    managed_paths = [
        state_relative,
        Path(".repoframe/state.schema.json"),
        Path(".repoframe/instructions.md"),
        *adapter_paths,
    ]
    for relative in managed_paths:
        _safe_target(repo, relative)
    state_path = _safe_target(repo, state_relative)
    planned: dict[Path, bytes] = {}
    changes: list[Change] = []

    if state_path.exists():
        payload, _, issues = load_and_validate(state_path)
        if issues or payload is None:
            details = "; ".join(issue.message for issue in issues)
            raise InitializationError(f"Existing state is invalid: {details}")
        existing_title = payload["goal"]["title"]
        if goal is not None and goal != existing_title:
            raise InitializationError(
                f"Existing state belongs to a different goal ('{existing_title}'); it was not replaced."
            )
        changes.append(Change(state_relative, "preserved"))
    else:
        if goal is None or not goal.strip():
            raise InitializationError("--goal is required when creating a new RepoFrame state.")
        payload = new_state(goal.strip(), outcome, criteria, constraints)
        state_issues = validate_state(payload)
        if state_issues:
            details = "; ".join(f"{issue.path}: {issue.message}" for issue in state_issues)
            raise InitializationError(f"New state fields are invalid: {details}")
        planned[state_relative] = (json.dumps(payload, indent=2, ensure_ascii=False) + "\n").encode("utf-8")

    managed_resources = {
        Path(".repoframe/state.schema.json"): _resource_text("state.schema.json").encode("utf-8"),
        Path(".repoframe/instructions.md"): _resource_text("instructions.md").encode("utf-8"),
    }
    planned.update(managed_resources)

    for relative in adapter_paths:
        target = repo / relative
        try:
            existing = target.read_text(encoding="utf-8") if target.exists() else ""
        except (OSError, UnicodeDecodeError) as exc:
            raise InitializationError(f"Unable to read agent instructions at {relative}: {exc}") from exc
        planned[relative] = _managed_text(existing, relative).encode("utf-8")

    for relative, content in list(planned.items()):
        target = repo / relative
        if target.exists() and target.read_bytes() == content:
            changes.append(Change(relative, "preserved"))
            del planned[relative]
        else:
            changes.append(Change(relative, "updated" if target.exists() else "created"))

    _write_batch(repo, planned)
    return changes
