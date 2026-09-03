from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from repoframe.agent import AgentError, CodexProvider, PromptRouter, UnsupportedProvider


class FakeProcess:
    def __init__(self, command: list[str], **kwargs: object) -> None:
        self.command = command
        self.returncode = 0
        self.output_path = Path(command[command.index("--output-last-message") + 1])
        self.output_path.write_text(
            json.dumps({"subject": "test: generated", "body": "", "summary": "Generated from the diff."}),
            encoding="utf-8",
        )

    def communicate(self, input: bytes | None = None, timeout: int | None = None):
        self.input = input
        self.timeout = timeout
        return b"", b""

    def poll(self):
        return self.returncode

    def terminate(self):
        self.returncode = -1

    def kill(self):
        self.returncode = -9


class AgentProviderTests(unittest.TestCase):
    def test_codex_provider_uses_ephemeral_read_only_structured_exec(self) -> None:
        calls: list[FakeProcess] = []

        def factory(command: list[str], **kwargs: object) -> FakeProcess:
            process = FakeProcess(command, **kwargs)
            calls.append(process)
            return process

        inspection = {"working_changes": {"files": [{"path": "app.py", "status": "modified"}]}}
        with tempfile.TemporaryDirectory() as temp_dir, patch(
            "repoframe.agent.subprocess.Popen", side_effect=factory
        ):
            provider = CodexProvider("codex")
            result = provider.generate_commit(Path(temp_dir), inspection)
        self.assertEqual("test: generated", result["subject"])
        command = calls[0].command
        self.assertIn("--ephemeral", command)
        self.assertEqual("read-only", command[command.index("--sandbox") + 1])
        self.assertEqual('approval_policy="never"', command[command.index("-c") + 1])
        self.assertIn("--output-schema", command)
        self.assertEqual("-", command[-1])
        self.assertIn(b"Changed paths", calls[0].input)

    def test_missing_and_unsupported_provider_have_explicit_codes(self) -> None:
        provider = CodexProvider(executable="")
        with self.assertRaises(AgentError) as caught:
            provider.generate_commit(
                Path("."),
                {"working_changes": {"files": [{"path": "a", "status": "modified"}]}},
            )
        self.assertEqual("provider_unavailable", caught.exception.code)
        with self.assertRaises(AgentError) as caught:
            UnsupportedProvider("claude").generate_commit(Path("."), {})
        self.assertEqual("provider_not_supported", caught.exception.code)

    def test_prompt_router_keeps_mode_contracts_distinct(self) -> None:
        commit = PromptRouter.commit(
            {"working_changes": {"files": [{"path": "a.py", "status": "modified"}]}}
        )
        self.assertIn("Do not write files", commit)
        self.assertIn("working-tree", commit)
        state = {
            "goal": {"title": "Ship"},
            "nodes": [],
            "interventions": [],
        }
        intervention = {"text": "Change direction"}
        routed = PromptRouter.intervention_triage(state, intervention)
        self.assertIn("preserve completed history", routed)
        self.assertIn("Graph Patch", routed)
