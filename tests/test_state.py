from __future__ import annotations

import json
import sys
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from repoframe.state import load_and_validate, new_state, slugify_goal, validate_state


def valid_state() -> dict:
    return {
        "$schema": "./state.schema.json",
        "schema_version": 1,
        "goal": {
            "id": "ship-auth",
            "title": "Ship authentication",
            "outcome": "Users can sign in safely.",
            "success_criteria": ["Authentication tests pass."],
            "constraints": ["No external identity provider."],
            "status": "active",
        },
        "nodes": [
            {
                "id": "inspect",
                "title": "Inspect the existing system",
                "status": "done",
                "depends_on": [],
                "summary": "Existing boundaries documented.",
                "evidence": ["src/auth.py"],
            },
            {
                "id": "implement",
                "title": "Implement authentication",
                "status": "active",
                "depends_on": ["inspect"],
            },
            {
                "id": "verify",
                "title": "Verify authentication",
                "status": "pending",
                "depends_on": ["implement"],
            },
        ],
        "updated_at": "2026-08-25T08:00:00Z",
    }


class StateValidationTests(unittest.TestCase):
    def assert_issue(self, payload: object, code: str) -> None:
        issues = validate_state(payload)
        self.assertIn(code, [issue.code for issue in issues], issues)

    def test_accepts_minimal_active_goal_with_no_nodes(self) -> None:
        payload = valid_state()
        payload["nodes"] = []
        self.assertEqual([], validate_state(payload))

    def test_accepts_valid_dag_with_done_dependency(self) -> None:
        self.assertEqual([], validate_state(valid_state()))

    def test_rejects_unknown_top_level_property(self) -> None:
        payload = valid_state()
        payload["notes"] = []
        self.assert_issue(payload, "schema.unknown_property")

    def test_rejects_unknown_nested_property(self) -> None:
        payload = valid_state()
        payload["nodes"][0]["owner"] = "agent"
        self.assert_issue(payload, "schema.unknown_property")

    def test_rejects_wrong_schema_version(self) -> None:
        payload = valid_state()
        payload["schema_version"] = 2
        self.assert_issue(payload, "schema.version")

    def test_rejects_non_string_status_values_without_crashing(self) -> None:
        payload = valid_state()
        payload["goal"]["status"] = {}
        payload["nodes"][0]["status"] = []
        codes = [issue.code for issue in validate_state(payload)]
        self.assertGreaterEqual(codes.count("schema.enum"), 2)

        done_payload = valid_state()
        done_payload["goal"]["status"] = "done"
        for node in done_payload["nodes"]:
            node["status"] = "done"
        done_payload["nodes"][0]["status"] = {}
        self.assertIn("schema.enum", [issue.code for issue in validate_state(done_payload)])

    def test_rejects_duplicate_node_ids(self) -> None:
        payload = valid_state()
        payload["nodes"][1]["id"] = "inspect"
        self.assert_issue(payload, "node.duplicate_id")

    def test_rejects_missing_dependency(self) -> None:
        payload = valid_state()
        payload["nodes"][1]["depends_on"] = ["missing"]
        self.assert_issue(payload, "dependency.not_found")

    def test_rejects_dependency_that_is_not_an_identifier(self) -> None:
        payload = valid_state()
        payload["nodes"][1]["depends_on"] = ["Invalid ID"]
        self.assert_issue(payload, "schema.identifier")

    def test_rejects_self_dependency(self) -> None:
        payload = valid_state()
        payload["nodes"][1]["depends_on"] = ["implement"]
        self.assert_issue(payload, "dependency.self")

    def test_rejects_cycle(self) -> None:
        payload = valid_state()
        payload["nodes"][0]["depends_on"] = ["verify"]
        self.assert_issue(payload, "dag.cycle")

    def test_rejects_multiple_active_nodes(self) -> None:
        payload = valid_state()
        payload["nodes"][2]["status"] = "active"
        self.assert_issue(payload, "node.multiple_active")

    def test_rejects_active_node_with_unfinished_dependency(self) -> None:
        payload = valid_state()
        payload["nodes"][0]["status"] = "pending"
        self.assert_issue(payload, "node.active_dependency")

    def test_accepts_active_node_with_skipped_dependency(self) -> None:
        payload = valid_state()
        payload["nodes"][0]["status"] = "skipped"
        self.assertEqual([], validate_state(payload))

    def test_rejects_done_goal_with_unfinished_node(self) -> None:
        payload = valid_state()
        payload["goal"]["status"] = "done"
        self.assert_issue(payload, "goal.incomplete_nodes")

    def test_rejects_timestamp_without_timezone(self) -> None:
        payload = valid_state()
        payload["updated_at"] = "2026-08-25T08:00:00"
        self.assert_issue(payload, "timestamp.timezone")

    def test_rejects_duplicate_dependency_entries(self) -> None:
        payload = valid_state()
        payload["nodes"][1]["depends_on"] = ["inspect", "inspect"]
        self.assert_issue(payload, "dependency.duplicate")

    def test_rejects_empty_optional_summary_and_evidence_item(self) -> None:
        payload = valid_state()
        payload["nodes"][0]["summary"] = ""
        payload["nodes"][0]["evidence"] = [""]
        codes = [issue.code for issue in validate_state(payload)]
        self.assertIn("schema.non_empty_string", codes)
        self.assertIn("schema.string_array", codes)

    def test_rejects_invalid_identifier(self) -> None:
        payload = valid_state()
        payload["goal"]["id"] = "Invalid ID"
        self.assert_issue(payload, "schema.identifier")

    def test_accepts_deep_acyclic_graph_without_recursion(self) -> None:
        payload = valid_state()
        payload["nodes"] = [
            {
                "id": f"node-{index:04d}",
                "title": f"Node {index}",
                "status": "pending",
                "depends_on": [f"node-{index + 1:04d}"] if index < 1499 else [],
            }
            for index in range(1500)
        ]
        self.assertEqual([], validate_state(payload))


class StateIOTests(unittest.TestCase):
    def test_load_reports_missing_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            _, raw, issues = load_and_validate(Path(temp_dir) / "missing.json")
        self.assertIsNone(raw)
        self.assertEqual("file.not_found", issues[0].code)

    def test_load_reports_invalid_json(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "state.json"
            path.write_text("{", encoding="utf-8")
            payload, raw, issues = load_and_validate(path)
        self.assertIsNone(payload)
        self.assertEqual(b"{", raw)
        self.assertEqual("json.invalid", issues[0].code)

    def test_load_returns_raw_bytes_and_valid_payload(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "state.json"
            path.write_text(json.dumps(valid_state()), encoding="utf-8")
            payload, raw, issues = load_and_validate(path)
        self.assertEqual([], issues)
        self.assertEqual(valid_state(), payload)
        self.assertIsInstance(raw, bytes)

    def test_new_state_uses_goal_defaults(self) -> None:
        payload = new_state("Ship Authentication", None, ["Tests pass"], ["No SaaS"])
        self.assertEqual("ship-authentication", payload["goal"]["id"])
        self.assertEqual("Ship Authentication", payload["goal"]["outcome"])
        self.assertEqual([], payload["nodes"])
        self.assertEqual([], validate_state(payload))

    def test_slugify_goal_falls_back_for_non_ascii_title(self) -> None:
        self.assertEqual("goal-1", slugify_goal("发布认证功能"))


if __name__ == "__main__":
    unittest.main()
