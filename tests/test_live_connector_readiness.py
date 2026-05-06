import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from eval_pipeline.live_connector_readiness import (
    DEFAULT_REQUIRED_CONTROLS,
    LIVE_CONNECTOR_READINESS_PLAN_TYPE,
    default_live_connectors,
    live_connector_readiness_plan,
    validate_live_connector_readiness_plan,
    write_live_connector_readiness_plan,
)


ROOT = Path(__file__).resolve().parents[1]


class LiveConnectorReadinessTests(unittest.TestCase):
    def test_plan_keeps_all_connectors_out_of_scope_for_local_rc(self):
        plan = live_connector_readiness_plan()
        validation = validate_live_connector_readiness_plan(plan)

        self.assertEqual(plan["plan_type"], LIVE_CONNECTOR_READINESS_PLAN_TYPE)
        self.assertTrue(validation["valid"], validation["issues"])
        self.assertFalse(plan["local_rc_scope"]["direct_live_connector_execution"])
        self.assertEqual(plan["summary"]["live_execution_enabled_count"], 0)
        self.assertEqual(plan["summary"]["out_of_scope_count"], plan["summary"]["connector_count"])
        self.assertGreaterEqual(plan["summary"]["connector_count"], 10)
        self.assertTrue(all(connector["scope_status"] == "out_of_scope_for_local_rc" for connector in plan["connectors"]))
        self.assertTrue(all(connector["live_execution_enabled"] is False for connector in plan["connectors"]))

    def test_each_connector_maps_auth_rate_limit_redaction_and_rollback(self):
        for connector in default_live_connectors():
            with self.subTest(connector_id=connector["connector_id"]):
                self.assertIsInstance(connector["auth_requirements"], dict)
                self.assertIsInstance(connector["rate_limits"], dict)
                self.assertIsInstance(connector["redaction"], dict)
                self.assertIsInstance(connector["rollback"], dict)
                self.assertFalse(connector["redaction"]["raw_private_content_allowed"])
                self.assertTrue(connector["rate_limits"]["idempotency_key_required"])
                self.assertEqual(connector["default_route"], "defer")
                for control in DEFAULT_REQUIRED_CONTROLS:
                    self.assertIn(control, connector["mi_gate_requirements"])

    def test_validation_rejects_live_execution_for_local_rc(self):
        connectors = default_live_connectors()
        connectors[0] = dict(connectors[0])
        connectors[0]["live_execution_enabled"] = True
        plan = live_connector_readiness_plan(connectors)

        validation = validate_live_connector_readiness_plan(plan)

        self.assertFalse(validation["valid"])
        messages = " ".join(issue["message"] for issue in validation["issues"])
        self.assertIn("Live execution must be disabled", messages)
        self.assertIn("Live execution count must be zero", messages)

    def test_write_plan_outputs_json(self):
        with tempfile.TemporaryDirectory() as directory:
            output_path = Path(directory) / "live_connector_readiness_plan.json"
            payload = write_live_connector_readiness_plan(output_path)
            written = json.loads(output_path.read_text(encoding="utf-8"))

        self.assertEqual(written, payload["plan"])
        self.assertTrue(payload["validation"]["valid"], payload["validation"]["issues"])
        self.assertGreater(payload["bytes"], 0)

    def test_live_connector_readiness_cli_writes_plan(self):
        with tempfile.TemporaryDirectory() as directory:
            output_path = Path(directory) / "live_connector_readiness_plan.json"
            completed = subprocess.run(
                [
                    sys.executable,
                    "scripts/live_connector_readiness.py",
                    "--output",
                    str(output_path),
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
            )
            written = json.loads(output_path.read_text(encoding="utf-8"))

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("pass -- connectors=", completed.stdout)
        self.assertEqual(written["summary"]["live_execution_enabled_count"], 0)


if __name__ == "__main__":
    unittest.main()
