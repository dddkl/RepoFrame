"""RepoFrame Long Run state creation, validation, and safe mutation."""

from __future__ import annotations

import copy
import json
import os
import re
import secrets
import tempfile
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


IDENTIFIER = re.compile(r"^[a-z0-9][a-z0-9_-]*$")
COMMON_TOP_LEVEL_FIELDS = {"$schema", "schema_version", "goal", "nodes", "updated_at"}
V2_TOP_LEVEL_FIELDS = {*COMMON_TOP_LEVEL_FIELDS, "interventions"}
GOAL_FIELDS = {"id", "title", "outcome", "success_criteria", "constraints", "status"}
NODE_FIELDS = {"id", "title", "status", "depends_on", "summary", "evidence"}
INTERVENTION_FIELDS = {"id", "target_node_id", "text", "status", "created_at", "result"}
INTERVENTION_RESULT_FIELDS = {"summary", "node_ids"}
GOAL_STATUSES = {"active", "done"}
NODE_STATUSES = {"pending", "active", "done", "blocked", "skipped"}
TERMINAL_NODE_STATUSES = {"done", "skipped"}
INTERVENTION_STATUSES = {"open", "resolving", "incorporated", "needs_user"}
UNRESOLVED_INTERVENTION_STATUSES = {"open", "resolving", "needs_user"}
PATCH_FIELDS = {"disposition", "summary", "goal_status", "add_nodes", "update_nodes", "result_node_ids"}
PATCH_UPDATE_FIELDS = {"id", "set"}
PATCH_MUTABLE_NODE_FIELDS = {"title", "status", "depends_on", "summary", "evidence"}


def utc_now() -> str:
    """Return a stable UTC timestamp suitable for the public protocol."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


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


class StateMutationError(RuntimeError):
    """Raised when a requested state mutation cannot produce a valid snapshot."""

    def __init__(self, message: str, issues: list[Issue] | None = None) -> None:
        super().__init__(message)
        self.issues = issues or []


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
        _issue(issues, "dependency.duplicate", path, "Identifiers must be unique.")
    return value


def _validate_timestamp(value: object, path: str, issues: list[Issue]) -> None:
    if not isinstance(value, str):
        _issue(issues, "schema.non_empty_string", path, "Expected an ISO 8601 timestamp string.")
        return
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        _issue(issues, "timestamp.invalid", path, "Expected a valid ISO 8601 timestamp.")
        return
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        _issue(issues, "timestamp.timezone", path, "Timestamp must include a timezone.")


def validate_state(payload: object) -> list[Issue]:
    """Validate a RepoFrame v1 or v2 state snapshot."""
    issues: list[Issue] = []
    if not isinstance(payload, dict):
        return [Issue("schema.object", "$", "Expected an object.")]

    version = payload.get("schema_version")
    is_v2 = version == 2 and not isinstance(version, bool)
    allowed = V2_TOP_LEVEL_FIELDS if is_v2 else COMMON_TOP_LEVEL_FIELDS
    required = V2_TOP_LEVEL_FIELDS if is_v2 else COMMON_TOP_LEVEL_FIELDS
    root = _required_object_fields(payload, "$", required, allowed, issues)
    assert root is not None

    if root.get("$schema") != "./state.schema.json":
        _issue(issues, "schema.reference", "$.$schema", "Expected './state.schema.json'.")
    if version not in {1, 2} or isinstance(version, bool):
        _issue(issues, "schema.version", "$.schema_version", "Only schema versions 1 and 2 are supported.")
    _validate_timestamp(root.get("updated_at"), "$.updated_at", issues)

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
                _issue(issues, "schema.identifier", dep_path, "Expected a lowercase dependency identifier.")
                continue
            if dependency == node_id:
                _issue(issues, "dependency.self", dep_path, "A node cannot depend on itself.")
            elif dependency not in node_by_id:
                _issue(issues, "dependency.not_found", dep_path, f"Dependency '{dependency}' does not exist.")
            elif isinstance(node_id, str) and node_id in adjacency:
                adjacency[node_id].append(dependency)
                if node.get("status") == "active" and not _is_terminal_status(node_by_id[dependency].get("status")):
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

    if is_v2:
        interventions = root.get("interventions")
        if not isinstance(interventions, list):
            _issue(issues, "schema.array", "$.interventions", "Expected an array.")
            return issues
        intervention_ids: set[str] = set()
        unresolved: list[str] = []
        for index, value in enumerate(interventions):
            path = f"$.interventions[{index}]"
            intervention = _required_object_fields(
                value,
                path,
                {"id", "target_node_id", "text", "status", "created_at"},
                INTERVENTION_FIELDS,
                issues,
            )
            if intervention is None:
                continue
            intervention_id = intervention.get("id")
            if _identifier(intervention_id, f"{path}.id", issues):
                if intervention_id in intervention_ids:
                    _issue(
                        issues,
                        "intervention.duplicate_id",
                        f"{path}.id",
                        f"Intervention id '{intervention_id}' is duplicated.",
                    )
                intervention_ids.add(intervention_id)
            target = intervention.get("target_node_id")
            if _identifier(target, f"{path}.target_node_id", issues) and target not in node_by_id:
                _issue(
                    issues,
                    "intervention.target_not_found",
                    f"{path}.target_node_id",
                    f"Target node '{target}' does not exist.",
                )
            _non_empty_string(intervention.get("text"), f"{path}.text", issues)
            _validate_timestamp(intervention.get("created_at"), f"{path}.created_at", issues)
            status = intervention.get("status")
            if not isinstance(status, str) or status not in INTERVENTION_STATUSES:
                _issue(issues, "schema.enum", f"{path}.status", "Unknown intervention status.")
            elif status in UNRESOLVED_INTERVENTION_STATUSES:
                unresolved.append(str(intervention_id))
            result = intervention.get("result")
            if status == "incorporated" and result is None:
                _issue(
                    issues,
                    "intervention.result_required",
                    f"{path}.result",
                    "An incorporated intervention requires a result.",
                )
            if result is not None:
                result_obj = _required_object_fields(
                    result,
                    f"{path}.result",
                    INTERVENTION_RESULT_FIELDS,
                    INTERVENTION_RESULT_FIELDS,
                    issues,
                )
                if result_obj is not None:
                    _non_empty_string(result_obj.get("summary"), f"{path}.result.summary", issues)
                    result_ids = _string_array(
                        result_obj.get("node_ids"), f"{path}.result.node_ids", issues, unique=True
                    )
                    if result_ids is not None:
                        for result_index, result_node_id in enumerate(result_ids):
                            if result_node_id not in node_by_id:
                                _issue(
                                    issues,
                                    "intervention.result_node_not_found",
                                    f"{path}.result.node_ids[{result_index}]",
                                    f"Result node '{result_node_id}' does not exist.",
                                )
        if goal is not None and goal.get("status") == "done" and unresolved:
            _issue(
                issues,
                "goal.unresolved_interventions",
                "$.goal.status",
                f"Done goal has unresolved interventions: {', '.join(unresolved)}",
            )
    return issues


def _find_cycle(adjacency: dict[str, list[str]]) -> list[str] | None:
    state = {node_id: 0 for node_id in adjacency}
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


def write_state_atomic(path: Path, payload: dict[str, Any]) -> None:
    """Validate and atomically replace a state snapshot."""
    issues = validate_state(payload)
    if issues:
        raise StateMutationError("State mutation produced an invalid snapshot.", issues)
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = (json.dumps(payload, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
    temporary: Path | None = None
    try:
        handle, name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
        temporary = Path(name)
        with os.fdopen(handle, "wb") as stream:
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        temporary = None
    except OSError as exc:
        raise StateMutationError(f"Unable to write state atomically: {exc}") from exc
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


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
    """Create a minimal RepoFrame v2 state snapshot."""
    return {
        "$schema": "./state.schema.json",
        "schema_version": 2,
        "goal": {
            "id": slugify_goal(title),
            "title": title,
            "outcome": outcome or title,
            "success_criteria": list(success_criteria),
            "constraints": list(constraints),
            "status": "active",
        },
        "nodes": [],
        "interventions": [],
        "updated_at": utc_now(),
    }


def migrate_to_v2(payload: dict[str, Any]) -> dict[str, Any]:
    """Return a v2 copy without mutating a valid v1 source."""
    migrated = copy.deepcopy(payload)
    if migrated.get("schema_version") == 1:
        migrated["schema_version"] = 2
        migrated["interventions"] = []
    return migrated


def add_intervention(payload: dict[str, Any], target_node_id: str, text: str) -> tuple[dict[str, Any], str]:
    """Create a durable intervention and reopen a completed goal when needed."""
    if not isinstance(text, str) or not text.strip():
        raise StateMutationError("Intervention text cannot be empty.")
    state = migrate_to_v2(payload)
    nodes = {node.get("id") for node in state.get("nodes", []) if isinstance(node, dict)}
    if target_node_id not in nodes:
        raise StateMutationError(f"Target node '{target_node_id}' does not exist.")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    intervention_id = f"intervention-{stamp}-{secrets.token_hex(2)}"
    existing_ids = {item.get("id") for item in state.get("interventions", []) if isinstance(item, dict)}
    while intervention_id in existing_ids:
        intervention_id = f"intervention-{stamp}-{secrets.token_hex(2)}"
    state["interventions"].append(
        {
            "id": intervention_id,
            "target_node_id": target_node_id,
            "text": text.strip(),
            "status": "open",
            "created_at": utc_now(),
        }
    )
    if state["goal"].get("status") == "done":
        state["goal"]["status"] = "active"
    state["updated_at"] = utc_now()
    issues = validate_state(state)
    if issues:
        raise StateMutationError("Unable to create intervention.", issues)
    return state, intervention_id


def set_intervention_status(
    payload: dict[str, Any],
    intervention_id: str,
    status: str,
    *,
    summary: str | None = None,
    node_ids: list[str] | None = None,
) -> dict[str, Any]:
    """Return a copy with one intervention status updated."""
    if status not in INTERVENTION_STATUSES:
        raise StateMutationError(f"Unknown intervention status: {status}")
    state = migrate_to_v2(payload)
    intervention = next((item for item in state["interventions"] if item.get("id") == intervention_id), None)
    if intervention is None:
        raise StateMutationError(f"Intervention '{intervention_id}' does not exist.")
    intervention["status"] = status
    if summary is not None:
        clean_summary = summary.strip()
        if not clean_summary:
            raise StateMutationError("Intervention result summary cannot be empty.")
        intervention["result"] = {"summary": clean_summary, "node_ids": list(node_ids or [])}
    elif status != "incorporated":
        intervention.pop("result", None)
    state["updated_at"] = utc_now()
    issues = validate_state(state)
    if issues:
        raise StateMutationError("Unable to update intervention.", issues)
    return state


def _patch_issue(path: str, message: str, code: str = "patch.invalid") -> StateMutationError:
    return StateMutationError(message, [Issue(code, path, message)])


def apply_graph_patch(payload: dict[str, Any], intervention_id: str, patch: object) -> dict[str, Any]:
    """Apply a constrained Graph Patch to a copy and validate the full result."""
    if not isinstance(patch, dict):
        raise _patch_issue("$", "Graph Patch must be an object.")
    unknown = set(patch) - PATCH_FIELDS
    if unknown:
        name = sorted(unknown)[0]
        raise _patch_issue(f"$.{name}", f"Unknown Graph Patch property '{name}'.")
    required = {"disposition", "summary", "add_nodes", "update_nodes", "result_node_ids"}
    missing = required - set(patch)
    if missing:
        name = sorted(missing)[0]
        raise _patch_issue(f"$.{name}", f"Required Graph Patch property '{name}' is missing.")
    disposition = patch.get("disposition")
    if disposition not in {"apply", "needs_user"}:
        raise _patch_issue("$.disposition", "Disposition must be 'apply' or 'needs_user'.")
    summary = patch.get("summary")
    if not isinstance(summary, str) or not summary.strip():
        raise _patch_issue("$.summary", "Graph Patch summary cannot be empty.")
    for field in ("add_nodes", "update_nodes", "result_node_ids"):
        if not isinstance(patch.get(field), list):
            raise _patch_issue(f"$.{field}", f"Graph Patch '{field}' must be an array.")

    state = migrate_to_v2(payload)
    intervention = next((item for item in state["interventions"] if item.get("id") == intervention_id), None)
    if intervention is None:
        raise _patch_issue("$.intervention_id", f"Intervention '{intervention_id}' does not exist.")
    if disposition == "needs_user":
        if patch["add_nodes"] or patch["update_nodes"] or patch["result_node_ids"]:
            raise _patch_issue("$", "A needs_user patch cannot include graph mutations.")
        return set_intervention_status(state, intervention_id, "needs_user", summary=summary, node_ids=[])

    nodes_by_id = {node["id"]: node for node in state["nodes"] if isinstance(node, dict) and "id" in node}
    for index, node in enumerate(patch["add_nodes"]):
        if not isinstance(node, dict):
            raise _patch_issue(f"$.add_nodes[{index}]", "Added node must be an object.")
        node_id = node.get("id")
        if not isinstance(node_id, str) or not IDENTIFIER.fullmatch(node_id):
            raise _patch_issue(f"$.add_nodes[{index}].id", "Added node has an invalid identifier.")
        if node_id in nodes_by_id:
            raise _patch_issue(f"$.add_nodes[{index}].id", f"Node '{node_id}' already exists.")
        copied = copy.deepcopy(node)
        state["nodes"].append(copied)
        nodes_by_id[node_id] = copied

    updated_ids: set[str] = set()
    for index, update in enumerate(patch["update_nodes"]):
        path = f"$.update_nodes[{index}]"
        if not isinstance(update, dict):
            raise _patch_issue(path, "Node update must be an object.")
        if set(update) != PATCH_UPDATE_FIELDS:
            raise _patch_issue(path, "Node update must contain exactly 'id' and 'set'.")
        node_id = update.get("id")
        if node_id in updated_ids:
            raise _patch_issue(f"{path}.id", f"Node '{node_id}' is updated more than once.")
        updated_ids.add(str(node_id))
        target = nodes_by_id.get(node_id)
        if target is None:
            raise _patch_issue(f"{path}.id", f"Node '{node_id}' does not exist.")
        if target.get("status") in TERMINAL_NODE_STATUSES:
            raise _patch_issue(f"{path}.id", f"Terminal node '{node_id}' cannot be rewritten.", "patch.terminal_node")
        changes = update.get("set")
        if not isinstance(changes, dict) or not changes:
            raise _patch_issue(f"{path}.set", "Node update fields cannot be empty.")
        unknown_fields = set(changes) - PATCH_MUTABLE_NODE_FIELDS
        if unknown_fields:
            field = sorted(unknown_fields)[0]
            raise _patch_issue(f"{path}.set.{field}", f"Node field '{field}' cannot be changed.")
        target.update(copy.deepcopy(changes))

    goal_status = patch.get("goal_status")
    if goal_status is not None:
        if goal_status not in GOAL_STATUSES:
            raise _patch_issue("$.goal_status", "Goal status must be 'active' or 'done'.")
        state["goal"]["status"] = goal_status

    result_node_ids = patch["result_node_ids"]
    if any(not isinstance(item, str) for item in result_node_ids) or len(result_node_ids) != len(set(result_node_ids)):
        raise _patch_issue("$.result_node_ids", "Result node identifiers must be unique strings.")
    intervention["status"] = "incorporated"
    intervention["result"] = {"summary": summary.strip(), "node_ids": list(result_node_ids)}
    state["updated_at"] = utc_now()
    issues = validate_state(state)
    if issues:
        raise StateMutationError("Graph Patch produced an invalid state.", issues)
    return state
