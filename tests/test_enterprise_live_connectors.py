import copy
import pathlib
import tempfile
import unittest

import aana
from eval_pipeline import enterprise_live_connectors
from scripts import aana_cli


SAFE_AANA_RESULT = {
    "gate_decision": "pass",
    "recommended_action": "accept",
    "aix": {"score": 0.97, "decision": "accept", "hard_blockers": []},
}


class EnterpriseLiveConnectorTests(unittest.TestCase):
    def test_default_config_validates_but_does_not_enable_writes(self):
        config = enterprise_live_connectors.default_enterprise_live_connector_config()
        validation = enterprise_live_connectors.validate_enterprise_live_connector_config(config)

        self.assertTrue(validation["valid"], validation)
        self.assertEqual(validation["summary"]["connector_count"], 3)
        self.assertEqual(validation["summary"]["write_enabled_count"], 0)
        self.assertEqual(
            set(validation["summary"]["required_connector_ids"]),
            {"crm_support", "email_send", "ticketing"},
        )

    def test_dry_run_write_never_executes_even_when_aana_accepts(self):
        connector = enterprise_live_connectors.build_enterprise_support_connectors()["email_send"]

        result = connector.send_email(
            email_action={"draft_ref": "redacted-draft-001", "recipient_ref": "redacted-recipient-001"},
            aana_result=SAFE_AANA_RESULT,
            mode="dry_run",
        )

        self.assertTrue(result["valid"], result)
        self.assertFalse(result["executed"])
        self.assertEqual(result["route"], "dry_run")
        self.assertFalse(result["raw_payload_logged"])
        self.assertIn("request_fingerprint", result)
        self.assertNotIn("redacted-draft-001", str(result))

    def test_write_fails_closed_when_aana_has_hard_blocker(self):
        connector = enterprise_live_connectors.build_enterprise_support_connectors()["ticketing"]
        unsafe = {
            "gate_decision": "pass",
            "recommended_action": "accept",
            "aix": {"score": 0.93, "decision": "accept", "hard_blockers": ["private_data_exposure"]},
        }

        result = connector.update_ticket(
            ticket_action={"ticket_ref": "redacted-ticket-001", "update_ref": "redacted-update-001"},
            aana_result=unsafe,
            mode="enforce",
        )

        self.assertFalse(result["valid"], result)
        self.assertFalse(result["executed"])
        self.assertIn("hard_blockers_present", result["blockers"])

    def test_live_approved_enforcement_calls_transport_for_email(self):
        config = enterprise_live_connectors.default_enterprise_live_connector_config()
        config = copy.deepcopy(config)
        for item in config["connectors"]:
            if item["connector_id"] == "email_send":
                item["approval_status"] = "live_approved"
                item["source_mode"] = "live"
                item["write_enabled"] = True
        calls = []

        def transport(manifest, payload):
            calls.append((manifest.connector_id, payload["operation"]))
            return {"status": "queued", "message_id": "msg-redacted-001", "request_id": "req-redacted-001"}

        connector = enterprise_live_connectors.build_enterprise_support_connectors(
            config,
            transports={"email_send": transport},
        )["email_send"]

        result = connector.send_email(
            email_action={"draft_ref": "redacted-draft-001", "recipient_ref": "redacted-recipient-001"},
            aana_result=SAFE_AANA_RESULT,
            mode="enforce",
        )

        self.assertTrue(result["valid"], result)
        self.assertTrue(result["executed"])
        self.assertEqual(result["route"], "accept")
        self.assertEqual(calls, [("email_send", "send_email")])
        self.assertEqual(result["response_metadata"]["message_id"], "msg-redacted-001")

    def test_support_case_shadow_read_calls_transport_when_live_approved(self):
        config = enterprise_live_connectors.default_enterprise_live_connector_config()
        config = copy.deepcopy(config)
        for item in config["connectors"]:
            if item["connector_id"] == "crm_support":
                item["approval_status"] = "live_approved"
                item["source_mode"] = "shadow"

        def transport(_manifest, _payload):
            return {
                "status": "ok",
                "evidence": [
                    {
                        "source_id": "crm-record",
                        "retrieved_at": "2026-05-05T00:00:00Z",
                        "trust_tier": "verified",
                        "redaction_status": "redacted",
                        "text": "Redacted support account facts.",
                    }
                ],
            }

        connector = enterprise_live_connectors.build_enterprise_support_connectors(
            config,
            transports={"crm_support": transport},
        )["crm_support"]

        result = connector.fetch_support_case(case_ref="redacted-case-001", mode="shadow")

        self.assertTrue(result["valid"], result)
        self.assertTrue(result["executed"])
        self.assertEqual(result["response_metadata"]["evidence_count"], 1)
        self.assertEqual(result["evidence"][0]["source_id"], "crm-record")

    def test_smoke_report_and_cli_are_available(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output = pathlib.Path(temp_dir) / "enterprise-live-connectors.json"
            code = aana_cli.main(["enterprise-live-connectors", "--mode", "dry_run", "--output", str(output)])

            self.assertEqual(code, 0)
            self.assertTrue(output.exists())
            report = enterprise_live_connectors.run_enterprise_support_connector_smoke(mode="dry_run")
            self.assertTrue(report["valid"], report)
            self.assertEqual(report["summary"]["executed_count"], 0)
            self.assertEqual(aana.ENTERPRISE_LIVE_CONNECTORS_VERSION, "0.1")


if __name__ == "__main__":
    unittest.main()
