"""Single-writer runtime for typed RepoFrame interactive operations."""

from __future__ import annotations

import secrets
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from .agent import AgentError, AgentProvider, make_provider
from .git_ops import GitOperationError, commit_all, push_current, working_tree_snapshot
from .mode import ModeError, get_mode, get_provider, is_git_repository, set_mode
from .state import (
    StateMutationError,
    add_intervention,
    apply_graph_patch,
    load_and_validate,
    set_intervention_status,
    write_state_atomic,
)


class OperationRequestError(RuntimeError):
    """A safe, typed error suitable for a local API response."""

    def __init__(self, message: str, *, code: str = "operation_invalid", status: int = 400) -> None:
        super().__init__(message)
        self.code = code
        self.status = status


@dataclass
class Operation:
    id: str
    type: str
    stage: str
    status: str = "queued"
    result: dict[str, Any] | None = None
    error: dict[str, Any] | None = None
    cancel_requested: bool = False
    thread: threading.Thread | None = field(default=None, repr=False)

    def public(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "id": self.id,
            "type": self.type,
            "status": self.status,
            "stage": self.stage,
        }
        if self.result is not None:
            payload["result"] = self.result
        if self.error is not None:
            payload["error"] = self.error
        return payload


class OperationManager:
    """Own one short-lived semantic or Git operation at a time."""

    def __init__(
        self,
        repo: Path,
        *,
        provider: AgentProvider | None = None,
        provider_factory: Callable[[str], AgentProvider] = make_provider,
        recover_interrupted: bool = True,
    ) -> None:
        self.repo = repo.resolve()
        self.state_path = self.repo / ".repoframe/state.json"
        self.provider_name = get_provider(self.repo)
        self.provider = provider or provider_factory(self.provider_name)
        self._lock = threading.RLock()
        self._operations: dict[str, Operation] = {}
        self._active_id: str | None = None
        self._proposals: dict[str, dict[str, Any]] = {}
        if recover_interrupted:
            self._recover_interrupted()

    def _recover_interrupted(self) -> None:
        payload, _, issues = load_and_validate(self.state_path)
        if issues or payload is None or payload.get("schema_version") != 2:
            return
        interrupted = [
            item["id"]
            for item in payload.get("interventions", [])
            if item.get("status") == "resolving"
        ]
        if not interrupted:
            return
        updated = payload
        for intervention_id in interrupted:
            updated = set_intervention_status(
                updated,
                intervention_id,
                "needs_user",
                summary="The previous operation ended before a valid Graph Patch was applied.",
                node_ids=[],
            )
        write_state_atomic(self.state_path, updated)

    def runtime(self, *, interactive: bool) -> dict[str, Any]:
        with self._lock:
            active = self._operations.get(self._active_id) if self._active_id else None
            git_available = is_git_repository(self.repo)
            provider_available = self.provider.available
            return {
                "interactive": interactive,
                "mode": get_mode(self.repo),
                "agent": {
                    "provider": self.provider_name,
                    "available": provider_available,
                    "status": "running" if active and active.status in {"queued", "running"} else "idle",
                },
                "operation": active.public() if active else None,
                "capabilities": {
                    "commit": interactive and git_available and provider_available,
                    "push": interactive and git_available and provider_available,
                    "intervention": interactive and provider_available and self.state_path.exists(),
                    "mode_switch": interactive and git_available and active is None,
                },
            }

    def switch_mode(self, mode: str) -> dict[str, str]:
        with self._lock:
            if self._active_id is not None:
                raise OperationRequestError(
                    "Mode cannot change while an operation Agent is running.",
                    code="agent_busy",
                    status=409,
                )
            try:
                set_mode(self.repo, mode)
            except ModeError as exc:
                raise OperationRequestError(str(exc), code="mode_unavailable", status=409) from exc
            return {"mode": mode}

    def get(self, operation_id: str) -> dict[str, Any]:
        with self._lock:
            operation = self._operations.get(operation_id)
            if operation is None:
                raise OperationRequestError("Operation was not found.", code="operation_not_found", status=404)
            return operation.public()

    def start(self, operation_type: str, payload: object) -> dict[str, Any]:
        if not isinstance(payload, dict):
            raise OperationRequestError("Operation payload must be an object.")
        allowed = {"git.prepare_commit", "git.commit", "git.commit_push", "intervention.create"}
        if operation_type not in allowed:
            raise OperationRequestError(f"Unknown operation type: {operation_type}")
        current_mode = get_mode(self.repo)
        if operation_type.startswith("git.") and current_mode != "iteration":
            raise OperationRequestError(
                "Commit operations are only available in Iteration.",
                code="wrong_mode",
                status=409,
            )
        if operation_type == "intervention.create" and current_mode != "long-run":
            raise OperationRequestError(
                "User interventions are only available in Long Run.",
                code="wrong_mode",
                status=409,
            )
        self._validate_payload(operation_type, payload)
        with self._lock:
            if self._active_id is not None:
                raise OperationRequestError(
                    "Another RepoFrame operation is already running.",
                    code="agent_busy",
                    status=409,
                )
            operation_id = f"operation-{secrets.token_hex(8)}"
            stage = {
                "git.prepare_commit": "Preparing commit",
                "git.commit": "Committing",
                "git.commit_push": "Committing",
                "intervention.create": "Analyzing intervention",
            }[operation_type]
            operation = Operation(operation_id, operation_type, stage)
            self._operations[operation_id] = operation
            self._active_id = operation_id
            thread = threading.Thread(
                target=self._run,
                args=(operation, dict(payload)),
                name=f"repoframe-{operation_id}",
                daemon=True,
            )
            operation.thread = thread
            thread.start()
            return operation.public()

    def _validate_payload(self, operation_type: str, payload: dict[str, Any]) -> None:
        if operation_type == "git.prepare_commit":
            if set(payload) - {"intent"}:
                raise OperationRequestError("Prepare commit accepts only 'intent'.")
            if payload.get("intent", "commit") not in {"commit", "commit_push"}:
                raise OperationRequestError("Commit intent must be 'commit' or 'commit_push'.")
            return
        if operation_type in {"git.commit", "git.commit_push"}:
            if set(payload) != {"proposal_id", "subject", "body"}:
                raise OperationRequestError("Commit confirmation requires proposal_id, subject, and body.")
            if not all(isinstance(payload[name], str) for name in ("proposal_id", "subject", "body")):
                raise OperationRequestError("Commit confirmation fields must be strings.")
            return
        if set(payload) != {"goal_id", "target_node_id", "text"}:
            raise OperationRequestError("Intervention requires goal_id, target_node_id, and text.")
        if not all(isinstance(payload[name], str) for name in ("goal_id", "target_node_id", "text")):
            raise OperationRequestError("Intervention fields must be strings.")
        if not payload["text"].strip():
            raise OperationRequestError("Intervention text cannot be empty.")

    def cancel(self, operation_id: str) -> dict[str, Any]:
        with self._lock:
            operation = self._operations.get(operation_id)
            if operation is None:
                raise OperationRequestError("Operation was not found.", code="operation_not_found", status=404)
            if operation.status not in {"queued", "running"}:
                return operation.public()
            operation.cancel_requested = True
            operation.stage = "Cancelling"
            self.provider.cancel()
            return operation.public()

    def close(self) -> None:
        with self._lock:
            active = self._operations.get(self._active_id) if self._active_id else None
            if active and active.status in {"queued", "running"}:
                active.cancel_requested = True
                self.provider.cancel()
        if active and active.thread:
            active.thread.join(timeout=5)

    def _run(self, operation: Operation, payload: dict[str, Any]) -> None:
        operation.status = "running"
        try:
            if operation.type == "git.prepare_commit":
                operation.result = self._prepare_commit(payload)
            elif operation.type in {"git.commit", "git.commit_push"}:
                operation.result = self._commit(operation, payload)
            else:
                operation.result = self._intervention(operation, payload)
            if operation.cancel_requested:
                operation.status = "cancelled"
                operation.error = {"code": "operation_cancelled", "message": "Operation was cancelled."}
                operation.result = None
            else:
                operation.status = "completed"
                operation.stage = "Complete"
        except (AgentError, GitOperationError, StateMutationError, OperationRequestError) as exc:
            operation.status = "cancelled" if operation.cancel_requested else "failed"
            code = getattr(exc, "code", "operation_failed")
            operation.error = {
                "code": "operation_cancelled" if operation.cancel_requested else code,
                "message": "Operation was cancelled." if operation.cancel_requested else str(exc),
            }
            issues = getattr(exc, "issues", None)
            if issues:
                operation.error["issues"] = [issue.to_dict() for issue in issues]
        except Exception:  # defensive boundary for the server thread
            operation.status = "failed"
            operation.error = {"code": "internal_error", "message": "Operation failed unexpectedly."}
        finally:
            with self._lock:
                if self._active_id == operation.id:
                    self._active_id = None

    def _prepare_commit(self, payload: dict[str, Any]) -> dict[str, Any]:
        snapshot = working_tree_snapshot(self.repo)
        changes = snapshot["inspection"]["working_changes"]
        if not changes["changed_files"]:
            raise GitOperationError("The working tree has no changes to commit.", code="no_changes")
        proposal = self.provider.generate_commit(self.repo, snapshot["inspection"])
        proposal_id = f"proposal-{secrets.token_hex(8)}"
        stored = {
            "fingerprint": snapshot["fingerprint"],
            "intent": payload.get("intent", "commit"),
        }
        with self._lock:
            self._proposals[proposal_id] = stored
        return {
            "proposal_id": proposal_id,
            "intent": stored["intent"],
            "subject": proposal["subject"],
            "body": proposal.get("body", ""),
            "summary": proposal["summary"],
            "working_changes": changes,
        }

    def _commit(self, operation: Operation, payload: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            proposal = self._proposals.get(payload["proposal_id"])
        if proposal is None:
            raise OperationRequestError(
                "Commit proposal was not found or has expired.",
                code="proposal_not_found",
                status=409,
            )
        commit = commit_all(
            self.repo,
            proposal["fingerprint"],
            payload["subject"],
            payload["body"],
        )
        with self._lock:
            self._proposals.pop(payload["proposal_id"], None)
        result: dict[str, Any] = {"commit": commit, "push": None}
        if operation.type == "git.commit_push":
            operation.stage = "Pushing"
            try:
                result["push"] = push_current(self.repo)
            except GitOperationError as exc:
                result["push"] = {"pushed": False, "code": exc.code, "message": str(exc)}
        return result

    def _intervention(self, operation: Operation, payload: dict[str, Any]) -> dict[str, Any]:
        state, _, issues = load_and_validate(self.state_path)
        if issues or state is None:
            raise StateMutationError("Current Long Run state is invalid.", issues)
        if state["goal"]["id"] != payload["goal_id"]:
            raise OperationRequestError(
                "Only the current Long Run Goal accepts interventions.",
                code="goal_read_only",
                status=409,
            )
        state, intervention_id = add_intervention(state, payload["target_node_id"], payload["text"])
        write_state_atomic(self.state_path, state)
        state = set_intervention_status(state, intervention_id, "resolving")
        write_state_atomic(self.state_path, state)
        intervention = next(item for item in state["interventions"] if item["id"] == intervention_id)
        try:
            triage = self.provider.triage_intervention(self.repo, state, intervention)
            if operation.cancel_requested:
                raise AgentError("Operation was cancelled.", code="operation_cancelled")
            route = triage.get("route")
            if route == "needs_user":
                patch: dict[str, Any] = {
                    "disposition": "needs_user",
                    "summary": triage.get("summary", "More user input is required."),
                    "add_nodes": [],
                    "update_nodes": [],
                    "result_node_ids": [],
                }
                updated = apply_graph_patch(state, intervention_id, patch)
                write_state_atomic(self.state_path, updated)
                return {"intervention_id": intervention_id, "disposition": "needs_user"}

            analyses: list[dict[str, Any]] = []
            if route == "parallel":
                requests = triage.get("analysis_requests")
                if not isinstance(requests, list) or not 1 <= len(requests) <= 2:
                    raise AgentError("Parallel triage must request one or two analyses.", code="invalid_agent_output")
                operation.stage = "Analyzing intervention"
                with ThreadPoolExecutor(max_workers=2, thread_name_prefix="repoframe-analysis") as executor:
                    analyses = list(executor.map(lambda request: self.provider.analyze(self.repo, request), requests))
                patch = self.provider.finalize_intervention(self.repo, state, intervention, analyses)
            elif route == "direct":
                patch = self.provider.finalize_intervention(self.repo, state, intervention, [])
            else:
                raise AgentError("Intervention triage returned an unknown route.", code="invalid_agent_output")

            operation.stage = "Updating execution path"
            try:
                updated = apply_graph_patch(state, intervention_id, patch)
            except StateMutationError as first_error:
                repair_issues = [issue.to_dict() for issue in first_error.issues]
                repaired = self.provider.finalize_intervention(
                    self.repo,
                    state,
                    intervention,
                    analyses,
                    repair_issues,
                )
                updated = apply_graph_patch(state, intervention_id, repaired)
            write_state_atomic(self.state_path, updated)
            incorporated = next(item for item in updated["interventions"] if item["id"] == intervention_id)
            return {
                "intervention_id": intervention_id,
                "disposition": incorporated["status"],
                "result": incorporated.get("result"),
            }
        except Exception as exc:
            current, _, current_issues = load_and_validate(self.state_path)
            if current is not None and not current_issues:
                summary = (
                    "The intervention could not be converted into a valid Graph Patch. "
                    f"{str(exc)[:300]}"
                )
                try:
                    failed = set_intervention_status(
                        current,
                        intervention_id,
                        "needs_user",
                        summary=summary,
                        node_ids=[],
                    )
                    write_state_atomic(self.state_path, failed)
                except StateMutationError:
                    pass
            raise
