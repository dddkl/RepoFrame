"""Short-lived, structured operation Agent providers."""

from __future__ import annotations

import json
import os
import signal
import shutil
import subprocess
import tempfile
import threading
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any


class AgentError(RuntimeError):
    """Raised when an operation Agent is unavailable or returns no safe result."""

    def __init__(self, message: str, *, code: str = "agent_failed", details: str = "") -> None:
        super().__init__(message)
        self.code = code
        self.details = details


NON_EMPTY_STRING = {"type": "string", "minLength": 1, "pattern": "\\S"}
STRING_ARRAY = {"type": "array", "items": NON_EMPTY_STRING}
NODE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["id", "title", "status", "depends_on", "summary", "evidence"],
    "properties": {
        "id": {"type": "string", "pattern": "^[a-z0-9][a-z0-9_-]*$"},
        "title": NON_EMPTY_STRING,
        "status": {"enum": ["pending", "active", "done", "blocked", "skipped"]},
        "depends_on": {
            "type": "array",
            "uniqueItems": True,
            "items": {"type": "string", "pattern": "^[a-z0-9][a-z0-9_-]*$"},
        },
        "summary": NON_EMPTY_STRING,
        "evidence": STRING_ARRAY,
    },
}
NODE_UPDATE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["id", "set"],
    "properties": {
        "id": {"type": "string", "pattern": "^[a-z0-9][a-z0-9_-]*$"},
        "set": {
            "type": "object",
            "additionalProperties": False,
            "required": ["title", "status", "depends_on", "summary", "evidence"],
            "properties": {
                "title": NON_EMPTY_STRING,
                "status": {"enum": ["pending", "active", "done", "blocked", "skipped"]},
                "depends_on": {
                    "type": "array",
                    "uniqueItems": True,
                    "items": {"type": "string", "pattern": "^[a-z0-9][a-z0-9_-]*$"},
                },
                "summary": NON_EMPTY_STRING,
                "evidence": STRING_ARRAY,
            },
        },
    },
}
GRAPH_PATCH_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "disposition",
        "summary",
        "goal_status",
        "add_nodes",
        "update_nodes",
        "result_node_ids"
    ],
    "properties": {
        "disposition": {"enum": ["apply", "needs_user"]},
        "summary": NON_EMPTY_STRING,
        "goal_status": {"enum": ["active", "done"]},
        "add_nodes": {"type": "array", "items": NODE_SCHEMA},
        "update_nodes": {"type": "array", "items": NODE_UPDATE_SCHEMA},
        "result_node_ids": {
            "type": "array",
            "uniqueItems": True,
            "items": {"type": "string", "pattern": "^[a-z0-9][a-z0-9_-]*$"},
        },
    },
}
COMMIT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["subject", "body", "summary"],
    "properties": {
        "subject": {"type": "string", "minLength": 1, "maxLength": 72, "pattern": "^[^\\r\\n]+$"},
        "body": {"type": "string"},
        "summary": NON_EMPTY_STRING,
    },
}
TRIAGE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["route", "summary", "analysis_requests"],
    "properties": {
        "route": {"enum": ["direct", "parallel", "needs_user"]},
        "summary": NON_EMPTY_STRING,
        "analysis_requests": {
            "type": "array",
            "maxItems": 2,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["id", "prompt"],
                "properties": {
                    "id": {"type": "string", "pattern": "^[a-z0-9][a-z0-9_-]*$"},
                    "prompt": NON_EMPTY_STRING,
                },
            },
        },
    },
}
ANALYSIS_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["summary", "findings"],
    "properties": {
        "summary": NON_EMPTY_STRING,
        "findings": STRING_ARRAY,
    },
}


class PromptRouter:
    """Build concise prompts without turning RepoFrame into a chat surface."""

    ITERATION_POLICY = (
        "Iteration is a fast human-review loop. Do not write files, change Git, or maintain RepoFrame state. "
        "Use the working tree as the source of truth and return only the requested structured result."
    )
    LONG_RUN_POLICY = (
        "Long Run models durable execution. Read repository and state facts, preserve completed history, and "
        "adjust the route through short design, development, and verification loops. Do not write files or Git. "
        "Return only the requested structured result and never include private reasoning."
    )

    @classmethod
    def commit(cls, inspection: dict[str, Any]) -> str:
        files = inspection["working_changes"]["files"]
        compact = [{"path": item["path"], "status": item["status"]} for item in files]
        return (
            f"{cls.ITERATION_POLICY}\n\n"
            "Generate one honest Git commit message for every current working-tree change. "
            "The backend will stage all tracked and untracked files after user confirmation. "
            "Inspect the repository and Git diff before deciding. Use an imperative subject of at most 72 characters. "
            "Use body only when it adds information not clear from the subject.\n\n"
            f"Changed paths:\n{json.dumps(compact, ensure_ascii=False, indent=2)}"
        )

    @classmethod
    def intervention_triage(cls, state: dict[str, Any], intervention: dict[str, Any]) -> str:
        return (
            f"{cls.LONG_RUN_POLICY}\n\n"
            "Triage the user intervention below. Choose direct when the route can be safely revised now. "
            "Choose parallel only when independent repository questions materially affect the patch, with at most "
            "two narrowly scoped read-only analysis requests. Choose needs_user only when essential intent is missing. "
            "Direct means no worker analysis is required; the final Graph Patch is requested separately. "
            "Never delete nodes, change IDs, or rewrite done/skipped nodes. "
            "For a completed target, add a corrective successor and rewire only unfinished downstream work.\n\n"
            f"State:\n{json.dumps(state, ensure_ascii=False, indent=2)}\n\n"
            f"Intervention:\n{json.dumps(intervention, ensure_ascii=False, indent=2)}"
        )

    @classmethod
    def worker(cls, request: dict[str, str]) -> str:
        return (
            f"{cls.LONG_RUN_POLICY}\n\n"
            "Perform only this scoped repository analysis. Return concise public findings; do not propose or apply edits.\n\n"
            f"{request['prompt']}"
        )

    @classmethod
    def intervention_final(
        cls,
        state: dict[str, Any],
        intervention: dict[str, Any],
        analyses: list[dict[str, Any]],
        validation_issues: list[dict[str, str]] | None = None,
    ) -> str:
        repair = ""
        if validation_issues:
            repair = (
                "\n\nA previous patch was rejected. Correct every issue without weakening the requested change:\n"
                + json.dumps(validation_issues, ensure_ascii=False, indent=2)
            )
        return (
            f"{cls.LONG_RUN_POLICY}\n\n"
            "Produce the final constrained Graph Patch for this intervention. Preserve terminal nodes. "
            "Every added node and every update set must include title, status, depends_on, a concise non-empty "
            "summary, and an evidence array; use an empty evidence array when none exists. "
            "Use needs_user only if no valid patch can express the user's intent. The full resulting state must have "
            "valid references, no cycles, at most one active node, and completed dependencies for any active node.\n\n"
            f"State:\n{json.dumps(state, ensure_ascii=False, indent=2)}\n\n"
            f"Intervention:\n{json.dumps(intervention, ensure_ascii=False, indent=2)}\n\n"
            f"Read-only analyses:\n{json.dumps(analyses, ensure_ascii=False, indent=2)}"
            f"{repair}"
        )


class AgentProvider(ABC):
    """Provider contract for semantic operations."""

    name: str

    @property
    @abstractmethod
    def available(self) -> bool:
        raise NotImplementedError

    @abstractmethod
    def generate_commit(self, repo: Path, inspection: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def triage_intervention(
        self, repo: Path, state: dict[str, Any], intervention: dict[str, Any]
    ) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def analyze(self, repo: Path, request: dict[str, str]) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def finalize_intervention(
        self,
        repo: Path,
        state: dict[str, Any],
        intervention: dict[str, Any],
        analyses: list[dict[str, Any]],
        validation_issues: list[dict[str, str]] | None = None,
    ) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def cancel(self) -> None:
        raise NotImplementedError


class CodexProvider(AgentProvider):
    """Codex CLI implementation using ephemeral, schema-constrained runs."""

    name = "codex"

    def __init__(self, executable: str | None = None) -> None:
        if executable is None:
            self.executable = shutil.which("codex.exe") if os.name == "nt" else shutil.which("codex")
        else:
            self.executable = executable
        self._processes: set[subprocess.Popen[bytes]] = set()
        self._lock = threading.Lock()

    @property
    def available(self) -> bool:
        return bool(self.executable)

    def _structured(self, repo: Path, prompt: str, schema: dict[str, Any], timeout: int) -> dict[str, Any]:
        if not self.executable:
            raise AgentError("Codex CLI was not found on PATH.", code="provider_unavailable")
        with tempfile.TemporaryDirectory(prefix="repoframe-agent-") as temp_dir:
            directory = Path(temp_dir)
            schema_path = directory / "output.schema.json"
            output_path = directory / "result.json"
            schema_path.write_text(json.dumps(schema, ensure_ascii=False), encoding="utf-8")
            command = [
                self.executable,
                "exec",
                "--ephemeral",
                "--color",
                "never",
                "--sandbox",
                "read-only",
                "-c",
                'approval_policy="never"',
                "--output-schema",
                str(schema_path),
                "--output-last-message",
                str(output_path),
                "-C",
                str(repo),
                "-",
            ]
            creationflags = 0
            if os.name == "nt":
                creationflags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
            try:
                process = subprocess.Popen(
                    command,
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    creationflags=creationflags,
                    start_new_session=os.name != "nt",
                )
            except OSError as exc:
                raise AgentError(f"Unable to start Codex CLI: {exc}", code="provider_unavailable") from exc
            with self._lock:
                self._processes.add(process)
            try:
                _, stderr = process.communicate(prompt.encode("utf-8"), timeout=timeout)
            except subprocess.TimeoutExpired as exc:
                self._stop_process(process, force=True)
                process.communicate()
                raise AgentError("Codex operation timed out.", code="agent_timeout") from exc
            finally:
                with self._lock:
                    self._processes.discard(process)
            if process.returncode:
                details = stderr.decode("utf-8", "replace").strip()
                raise AgentError("Codex operation failed.", details=details)
            try:
                result = json.loads(output_path.read_text(encoding="utf-8"))
            except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise AgentError("Codex did not return a valid structured result.", code="invalid_agent_output") from exc
            if not isinstance(result, dict):
                raise AgentError("Codex structured result must be an object.", code="invalid_agent_output")
            return result

    def generate_commit(self, repo: Path, inspection: dict[str, Any]) -> dict[str, Any]:
        return self._structured(repo, PromptRouter.commit(inspection), COMMIT_SCHEMA, 300)

    def triage_intervention(
        self, repo: Path, state: dict[str, Any], intervention: dict[str, Any]
    ) -> dict[str, Any]:
        return self._structured(
            repo,
            PromptRouter.intervention_triage(state, intervention),
            TRIAGE_SCHEMA,
            900,
        )

    def analyze(self, repo: Path, request: dict[str, str]) -> dict[str, Any]:
        return self._structured(repo, PromptRouter.worker(request), ANALYSIS_SCHEMA, 900)

    def finalize_intervention(
        self,
        repo: Path,
        state: dict[str, Any],
        intervention: dict[str, Any],
        analyses: list[dict[str, Any]],
        validation_issues: list[dict[str, str]] | None = None,
    ) -> dict[str, Any]:
        return self._structured(
            repo,
            PromptRouter.intervention_final(state, intervention, analyses, validation_issues),
            GRAPH_PATCH_SCHEMA,
            900,
        )

    def cancel(self) -> None:
        with self._lock:
            processes = list(self._processes)
        for process in processes:
            if process.poll() is None:
                self._stop_process(process)

    @staticmethod
    def _stop_process(process: subprocess.Popen[bytes], *, force: bool = False) -> None:
        if os.name == "nt":
            process.kill() if force else process.terminate()
            return
        try:
            os.killpg(process.pid, signal.SIGKILL if force else signal.SIGTERM)
        except ProcessLookupError:
            return


class UnsupportedProvider(AgentProvider):
    """Explicit diagnostic for providers whose bridge is not implemented yet."""

    def __init__(self, name: str) -> None:
        self.name = name

    @property
    def available(self) -> bool:
        return False

    def _unsupported(self) -> dict[str, Any]:
        raise AgentError(
            f"The '{self.name}' operation provider is not implemented in this release.",
            code="provider_not_supported",
        )

    def generate_commit(self, repo: Path, inspection: dict[str, Any]) -> dict[str, Any]:
        return self._unsupported()

    def triage_intervention(
        self, repo: Path, state: dict[str, Any], intervention: dict[str, Any]
    ) -> dict[str, Any]:
        return self._unsupported()

    def analyze(self, repo: Path, request: dict[str, str]) -> dict[str, Any]:
        return self._unsupported()

    def finalize_intervention(
        self,
        repo: Path,
        state: dict[str, Any],
        intervention: dict[str, Any],
        analyses: list[dict[str, Any]],
        validation_issues: list[dict[str, str]] | None = None,
    ) -> dict[str, Any]:
        return self._unsupported()

    def cancel(self) -> None:
        return


def make_provider(name: str) -> AgentProvider:
    """Create a configured provider without accepting arbitrary command templates."""
    if name == "codex":
        return CodexProvider()
    return UnsupportedProvider(name)
