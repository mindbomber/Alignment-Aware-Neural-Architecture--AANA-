import json
import pathlib
import tempfile
import unittest

import aana
from eval_pipeline import agent_api, agent_server
from scripts import aana_cli


ROOT = pathlib.Path(__file__).resolve().parents[1]


def decision_surface(result):
    return {
        "gate_decision": result.get("gate_decision"),
        "recommended_action": result.get("recommended_action"),
        "candidate_gate": result.get("candidate_gate"),
        "aix_decision": result.get("aix", {}).get("decision"),
        "candidate_aix_decision": result.get("candidate_aix", {}).get("decision"),
        "violation_codes": [item.get("code") for item in result.get("violations", [])],
    }


class RuntimeBoundaryCleanupTests(unittest.TestCase):
    def test_cli_gallery_run_uses_workflow_contract_shape(self):
        gallery = aana_cli.load_gallery(aana_cli.DEFAULT_GALLERY)
        entry = aana_cli.find_entry(gallery, "support_reply")

        result = aana_cli.run_entry(entry)

        self.assertEqual(result["contract_version"], "0.1")
        self.assertEqual(result["workflow_id"], "gallery-support_reply")
        self.assertEqual(result["adapter"], "support_reply")
        self.assertIn("raw_result", result)
        self.assertIn("agent_check_version", result["raw_result"])
        self.assertNotIn("final_answer", result)

    def test_cli_gallery_run_matches_workflow_api_decision_surface(self):
        gallery = aana_cli.load_gallery(aana_cli.DEFAULT_GALLERY)
        entry = aana_cli.find_entry(gallery, "research_summary")
        workflow_request = aana_cli.workflow_request_from_gallery_entry(entry)

        cli_result = aana_cli.run_entry(entry)
        api_result = agent_api.check_workflow_request(workflow_request)

        self.assertEqual(decision_surface(cli_result), decision_surface(api_result))

    def test_python_sdk_and_http_workflow_route_return_same_decision_surface(self):
        workflow_request = agent_api.load_json_file(ROOT / "examples" / "workflow_research_summary.json")

        sdk_result = aana.check_request(workflow_request)
        status, http_result = agent_server.route_request(
            "POST",
            "/workflow-check",
            json.dumps(workflow_request).encode("utf-8"),
        )

        self.assertEqual(status, 200)
        self.assertEqual(decision_surface(sdk_result), decision_surface(http_result))

    def test_playground_check_wraps_canonical_workflow_result_and_audit_preview(self):
        workflow_request = agent_api.load_json_file(ROOT / "examples" / "workflow_research_summary.json")

        with tempfile.TemporaryDirectory() as tmp:
            audit_log = pathlib.Path(tmp) / "playground.jsonl"
            status, payload = agent_server.route_request(
                "POST",
                "/playground/check",
                json.dumps(workflow_request).encode("utf-8"),
                audit_log_path=audit_log,
            )

        direct_result = agent_api.check_workflow_request(workflow_request)

        self.assertEqual(status, 200)
        self.assertEqual(payload["runtime_boundary"]["public_api"], "workflow_contract")
        self.assertEqual(payload["runtime_boundary"]["canonical_route"], "/workflow-check")
        self.assertEqual(decision_surface(payload["result"]), decision_surface(direct_result))
        self.assertEqual(payload["audit_record"]["record_type"], "workflow_check")
        self.assertEqual(payload["audit_record"]["gate_decision"], payload["result"]["gate_decision"])
        self.assertEqual(payload["audit_record"]["recommended_action"], payload["result"]["recommended_action"])
        self.assertEqual(payload["audit_record"]["aix"]["decision"], payload["result"]["aix"]["decision"])

    def test_agent_event_and_workflow_contract_surfaces_share_adapter_decisions(self):
        workflow_request = agent_api.load_json_file(ROOT / "examples" / "workflow_research_summary.json")
        event = {
            "event_version": "0.1",
            "event_id": workflow_request["workflow_id"],
            "agent": "workflow",
            "adapter_id": workflow_request["adapter"],
            "user_request": workflow_request["request"],
            "candidate_action": workflow_request["candidate"],
            "available_evidence": workflow_request["evidence"] + [
                f"Constraint to preserve: {constraint}"
                for constraint in workflow_request.get("constraints", [])
            ],
            "allowed_actions": workflow_request.get("allowed_actions"),
            "metadata": {"surface": "runtime_boundary_test"},
        }

        workflow_result = agent_api.check_workflow_request(workflow_request)
        event_result = agent_api.check_event(event)

        self.assertEqual(workflow_result["gate_decision"], event_result["gate_decision"])
        self.assertEqual(workflow_result["candidate_gate"], event_result["candidate_gate"])
        self.assertEqual(workflow_result["recommended_action"], event_result["recommended_action"])
        self.assertEqual(workflow_result["aix"]["decision"], event_result["aix"]["decision"])


if __name__ == "__main__":
    unittest.main()
