from __future__ import annotations

import json
import sys
import unittest
from importlib import resources
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))


class SchemaResourceTests(unittest.TestCase):
    def test_packaged_schema_describes_v1_and_v2_contracts(self) -> None:
        text = resources.files("repoframe.resources").joinpath("state.schema.json").read_text(encoding="utf-8")
        schema = json.loads(text)
        self.assertEqual("https://json-schema.org/draft/2020-12/schema", schema["$schema"])
        self.assertEqual(2, len(schema["oneOf"]))
        self.assertEqual(1, schema["$defs"]["stateV1"]["properties"]["schema_version"]["const"])
        self.assertEqual(2, schema["$defs"]["stateV2"]["properties"]["schema_version"]["const"])
        self.assertFalse(schema["$defs"]["stateV2"]["additionalProperties"])
        self.assertIn("interventions", schema["$defs"]["stateV2"]["required"])
        self.assertEqual(
            ["pending", "active", "done", "blocked", "skipped"],
            schema["$defs"]["node"]["properties"]["status"]["enum"],
        )


if __name__ == "__main__":
    unittest.main()
