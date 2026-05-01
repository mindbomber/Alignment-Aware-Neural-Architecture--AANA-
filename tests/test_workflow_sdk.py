import json
import pathlib
import unittest

import aana
from eval_pipeline import agent_api, agent_server, workflow_contract


ROOT = pathlib.Path(__file__).resolve().parents[1]


class WorkflowSdkTests(unittest.TestCase):
    def test_sdk_check_returns_workflow_result(self):
        result = aana.check(
            adapter="research_summary",
            request="Write a concise research brief. Use only Source A and Source B. Label uncertainty.",
            candidate="This is proven to improve productivity by 40% for all teams [Source C].",
            evidence=[
                "Source A: AANA makes constraints explicit.",
                "Source B: Source coverage can be incomplete.",
            ],
            constraints=["Do not invent citations.", "Do not add unsupported numbers."],
            workflow_id="test-workflow-001",
        )

        self.assertEqual(result["contract_version"], "0.1")
        self.assertEqual(result["adapter"], "research_summary")
        self.assertEqual(result["workflow_id"], "test-workflow-001")
        self.assertEqual(result["candidate_gate"], "block")
        self.assertEqual(result["gate_decision"], "pass")
        self.assertEqual(result["recommended_action"], "revise")
        self.assertTrue(result["violations"])
        self.assertIn("Grounded research summary", result["output"])

    def test_validate_workflow_request_reports_missing_adapter(self):
        report = aana.validate_workflow_request({"request": "Draft a summary."})

        self.assertFalse(report["valid"])
        self.assertEqual(report["errors"], 1)
        self.assertIn("adapter", report["issues"][0]["path"])

    def test_workflow_request_file_checks(self):
        workflow_request = agent_api.load_json_file(ROOT / "examples" / "workflow_research_summary.json")

        validation = agent_api.validate_workflow_request(workflow_request)
        result = agent_api.check_workflow_request(workflow_request)

        self.assertTrue(validation["valid"], validation)
        self.assertEqual(result["gate_decision"], "pass")
        self.assertEqual(result["recommended_action"], "revise")
        self.assertEqual(result["adapter"], "research_summary")

    def test_schema_catalog_includes_workflow_schemas(self):
        schemas = aana.schema_catalog()

        self.assertIn("workflow_request", schemas)
        self.assertIn("workflow_result", schemas)
        self.assertEqual(schemas["workflow_request"]["title"], "AANA Workflow Request")

    def test_workflow_contract_converts_to_agent_event(self):
        workflow_request = workflow_contract.normalize_workflow_request(
            adapter="research_summary",
            request="Summarize sources.",
            candidate="Unsupported answer.",
            evidence="Source A: verified.",
            constraints=["Use Source A only."],
            workflow_id="workflow-123",
        )

        event = workflow_contract.workflow_request_to_agent_event(workflow_request)

        self.assertEqual(event["adapter_id"], "research_summary")
        self.assertEqual(event["event_id"], "workflow-123")
        self.assertIn("Source A: verified.", event["available_evidence"])
        self.assertIn("Constraint to preserve: Use Source A only.", event["available_evidence"])

    def test_http_workflow_routes(self):
        workflow_request = agent_api.load_json_file(ROOT / "examples" / "workflow_research_summary.json")

        status, payload = agent_server.route_request(
            "POST",
            "/workflow-check",
            json.dumps(workflow_request).encode("utf-8"),
        )

        self.assertEqual(status, 200)
        self.assertEqual(payload["gate_decision"], "pass")
        self.assertEqual(payload["recommended_action"], "revise")

    def test_http_workflow_schema_route(self):
        status, payload = agent_server.route_request("GET", "/schemas/workflow-request.schema.json")

        self.assertEqual(status, 200)
        self.assertEqual(payload["title"], "AANA Workflow Request")
        self.assertIn("adapter", payload["properties"])


if __name__ == "__main__":
    unittest.main()
