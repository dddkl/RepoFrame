"""RepoFrame state creation, loading, and validation."""

from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


IDENTIFIER = re.compile(r"^[a-z0-9][a-z0-9_-]*$")
TOP_LEVEL_FIELDS = {"$schema", "schema_version", "goal", "nodes", "updated_at"}
GOAL_FIELDS = {"id", "title", "outcome", "success_criteria", "constraints", "status"}
NODE_FIELDS = {"id", "title", "status", "depends_on", "summary", "evidence"}
GOAL_STATUSES = {"active", "done"}
NODE_STATUSES = {"pending", "active", "done", "blocked", "skipped"}
TERMINAL_NODE_STATUSES = {"done", "skipped"}


def _is_terminal_status(value: object) -> bool:
    return isinstance(value, str) and value in TERMINAL_NODE_STATUSES


@dataclass(frozen=True)
class Issue:
    """A stable, machine-readable state validation issue."""

    code: str
    path: str
    message: str

    def to_dict(self) -> dict[str, str]:
        return {"code": self.code, "path": self.path, "message": self.message}


def _issue(issues: list[Issue], code: str, path: str, message: str) -> None:
    issues.append(Issue(code, path, message))


def _required_object_fields(
    value: object,
    path: str,
    required: set[str],
    allowed: set[str],
    issues: list[Issue],
) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        _issue(issues, "schema.object", path, "Expected an object.")
        return None
    for name in sorted(required - set(value)):
        _issue(issues, "schema.required", f"{path}.{name}", f"Required property '{name}' is missing.")
    for name in sorted(set(value) - allowed):
        _issue(issues, "schema.unknown_property", f"{path}.{name}", f"Unknown property '{name}'.")
    return value


def _non_empty_string(value: object, path: str, issues: list[Issue]) -> bool:
    if not isinstance(value, str) or not value.strip():
        _issue(issues, "schema.non_empty_string", path, "Expected a non-empty string.")
        return False
    return True


def _identifier(value: object, path: str, issues: list[Issue]) -> bool:
    if not isinstance(value, str) or not IDENTIFIER.fullmatch(value):
        _issue(
            issues,
            "schema.identifier",
            path,
            "Expected a lowercase identifier containing letters, numbers, hyphens, or underscores.",
        )
        return False
    return True


def _string_array(value: object, path: str, issues: list[Issue], *, unique: bool = False) -> list[str] | None:
    if not isinstance(value, list) or any(not isinstance(item, str) or not item.strip() for item in value):
        _issue(issues, "schema.string_array", path, "Expected an array of non-empty strings.")
        return None
    if unique and len(value) != len(set(value)):
        _issue(issues, "dependency.duplicate", path, "Dependency identifiers must be unique.")
    return value


def _validate_timestamp(value: object, issues: list[Issue]) -> None:
    if not isinstance(value, str):
        _issue(issues, "schema.non_empty_string", "$.updated_at", "Expected an ISO 8601 timestamp string.")
        return
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        _issue(issues, "timestamp.invalid", "$.updated_at", "Expected a valid ISO 8601 timestamp.")
        return
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        _issue(issues, "timestamp.timezone", "$.updated_at", "Timestamp must include a timezone.")


def validate_state(payload: object) -> list[Issue]:
    """Validate a RepoFrame v1 state snapshot."""
    issues: list[Issue] = []
    root = _required_object_fields(payload, "$", TOP_LEVEL_FIELDS, TOP_LEVEL_FIELDS, issues)
    if root is None:
        return issues

    if root.get("$schema") != "./state.schema.json":
        _issue(issues, "schema.reference", "$.$schema", "Expected './state.schema.json'.")
    if root.get("schema_version") != 1 or isinstance(root.get("schema_version"), bool):
        _issue(issues, "schema.version", "$.schema_version", "Only schema version 1 is supported.")
    _validate_timestamp(root.get("updated_at"), issues)

    goal = _required_object_fields(root.get("goal"), "$.goal", GOAL_FIELDS, GOAL_FIELDS, issues)
    if goal is not None:
        _identifier(goal.get("id"), "$.goal.id", issues)
        _non_empty_string(goal.get("title"), "$.goal.title", issues)
        _non_empty_string(goal.get("outcome"), "$.goal.outcome", issues)
        _string_array(goal.get("success_criteria"), "$.goal.success_criteria", issues)
        _string_array(goal.get("constraints"), "$.goal.constraints", issues)
        goal_status = goal.get("status")
        if not isinstance(goal_status, str) or goal_status not in GOAL_STATUSES:
            _issue(issues, "schema.enum", "$.goal.status", "Expected 'active' or 'done'.")

    nodes_value = root.get("nodes")
    if not isinstance(nodes_value, list):
        _issue(issues, "schema.array", "$.nodes", "Expected an array.")
        return issues

    nodes: list[dict[str, Any]] = []
    ids: dict[str, int] = {}
    active_indexes: list[int] = []
    for index, value in enumerate(nodes_value):
        path = f"$.nodes[{index}]"
        node = _required_object_fields(value, path, {"id", "title", "status", "depends_on"}, NODE_FIELDS, issues)
        if node is None:
            continue
        nodes.append(node)
        node_id = node.get("id")
        if _identifier(node_id, f"{path}.id", issues):
            if node_id in ids:
                _issue(issues, "node.duplicate_id", f"{path}.id", f"Node id '{node_id}' is duplicated.")
            else:
                ids[node_id] = index
        _non_empty_string(node.get("title"), f"{path}.title", issues)
        node_status = node.get("status")
        if not isinstance(node_status, str) or node_status not in NODE_STATUSES:
            _issue(issues, "schema.enum", f"{path}.status", "Unknown node status.")
        elif node_status == "active":
            active_indexes.append(index)
        _string_array(node.get("depends_on"), f"{path}.depends_on", issues, unique=True)
        if "summary" in node:
            _non_empty_string(node["summary"], f"{path}.summary", issues)
        if "evidence" in node:
            _string_array(node["evidence"], f"{path}.evidence", issues)

    if len(active_indexes) > 1:
        _issue(issues, "node.multiple_active", "$.nodes", "At most one node may be active.")

    node_by_id = {
        node["id"]: node
        for node in nodes
        if isinstance(node.get("id"), str) and IDENTIFIER.fullmatch(node["id"]) and node["id"] in ids
    }
    adjacency: dict[str, list[str]] = {node_id: [] for node_id in node_by_id}
    for index, node in enumerate(nodes_value):
        if not isinstance(node, dict) or not isinstance(node.get("depends_on"), list):
            continue
        node_id = node.get("id")
        for dep_index, dependency in enumerate(node["depends_on"]):
            dep_path = f"$.nodes[{index}].depends_on[{dep_index}]"
            if not isinstance(dependency, str):
                continue
            if not IDENTIFIER.fullmatch(dependency):
                _issue(
                    issues,
                    "schema.identifier",
                    dep_path,
                    "Expected a lowercase identifier containing letters, numbers, hyphens, or underscores.",
                )
                continue
            if dependency == node_id:
                _issue(issues, "dependency.self", dep_path, "A node cannot depend on itself.")
            elif dependency not in node_by_id:
                _issue(issues, "dependency.not_found", dep_path, f"Dependency '{dependency}' does not exist.")
            elif isinstance(node_id, str) and node_id in adjacency:
                adjacency[node_id].append(dependency)
                dependency_status = node_by_id[dependency].get("status")
                if node.get("status") == "active" and not _is_terminal_status(dependency_status):
                    _issue(
                        issues,
                        "node.active_dependency",
                        dep_path,
                        f"Active node dependency '{dependency}' is not done or skipped.",
                    )

    cycle = _find_cycle(adjacency)
    if cycle:
        _issue(issues, "dag.cycle", "$.nodes", f"Dependency cycle detected: {' -> '.join(cycle)}")

    if goal is not None and goal.get("status") == "done":
        unfinished = [
            node.get("id", f"index-{index}")
            for index, node in enumerate(nodes_value)
            if isinstance(node, dict) and not _is_terminal_status(node.get("status"))
        ]
        if unfinished:
            _issue(
                issues,
                "goal.incomplete_nodes",
                "$.goal.status",
                f"Done goal has unfinished nodes: {', '.join(map(str, unfinished))}",
            )
    return issues


def _find_cycle(adjacency: dict[str, list[str]]) -> list[str] | None:
    state = {node_id: 0 for node_id in adjacency}  # 0 unseen, 1 visiting, 2 complete
    for start in sorted(adjacency):
        if state[start] != 0:
            continue
        stack: list[tuple[str, int]] = [(start, 0)]
        path: list[str] = []
        while stack:
            node_id, dependency_index = stack[-1]
            if state[node_id] == 0:
                state[node_id] = 1
                path.append(node_id)
            dependencies = adjacency.get(node_id, [])
            if dependency_index < len(dependencies):
                dependency = dependencies[dependency_index]
                stack[-1] = (node_id, dependency_index + 1)
                if state[dependency] == 0:
                    stack.append((dependency, 0))
                elif state[dependency] == 1:
                    cycle_start = path.index(dependency)
                    return [*path[cycle_start:], dependency]
                continue
            stack.pop()
            path.pop()
            state[node_id] = 2
    return None


def load_and_validate(path: Path) -> tuple[dict[str, Any] | None, bytes | None, list[Issue]]:
    """Read and validate a state file while preserving its raw bytes for ETags."""
    try:
        raw = path.read_bytes()
    except FileNotFoundError:
        return None, None, [Issue("file.not_found", "$", f"State file not found: {path}")]
    except OSError as exc:
        return None, None, [Issue("file.read", "$", f"Unable to read state file: {exc}")]
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        return None, raw, [Issue("json.invalid", "$", f"Invalid UTF-8 JSON: {exc}")]
    issues = validate_state(payload)
    return payload if isinstance(payload, dict) else None, raw, issues


def slugify_goal(title: str) -> str:
    """Create a deterministic ASCII goal identifier."""
    normalized = unicodedata.normalize("NFKD", title).encode("ascii", "ignore").decode("ascii").lower()
    slug = re.sub(r"[^a-z0-9]+", "-", normalized).strip("-")
    return slug or "goal-1"


def new_state(
    title: str,
    outcome: str | None,
    success_criteria: list[str],
    constraints: list[str],
) -> dict[str, Any]:
    """Create a minimal RepoFrame v1 state snapshot."""
    timestamp = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    return {
        "$schema": "./state.schema.json",
        "schema_version": 1,
        "goal": {
            "id": slugify_goal(title),
            "title": title,
            "outcome": outcome or title,
            "success_criteria": list(success_criteria),
            "constraints": list(constraints),
            "status": "active",
        },
        "nodes": [],
        "updated_at": timestamp,
    }
