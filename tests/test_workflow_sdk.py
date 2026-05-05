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
        self.assertEqual(result["aix"]["decision"], "accept")
        self.assertIn("candidate_aix", result)

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

    def test_sdk_check_file_and_result_object(self):
        result = aana.check_file(ROOT / "examples" / "workflow_research_summary.json")
        result_object = aana.result_object(result)

        self.assertTrue(result_object.passed)
        self.assertEqual(result_object.adapter, "research_summary")
        self.assertEqual(result_object.recommended_action, "revise")
        self.assertEqual(result_object.aix["decision"], "accept")

    def test_sdk_check_batch_file_and_result_object(self):
        result = aana.check_batch_file(ROOT / "examples" / "workflow_batch_productive_work.json")
        result_object = aana.batch_result_object(result)

        self.assertTrue(result_object.passed)
        self.assertEqual(result_object.batch_id, "demo-batch-productive-work-001")
        self.assertEqual(result_object.summary["total"], 3)
        self.assertEqual(result_object.summary["recommended_actions"]["revise"], 3)

    def test_sdk_check_batch_accepts_typed_batch(self):
        batch = aana.WorkflowBatchRequest(
            requests=[
                aana.WorkflowRequest(
                    adapter="research_summary",
                    request="Write a concise research brief. Use only Source A and Source B.",
                    candidate="AANA improves productivity by 40% for all teams [Source C].",
                    evidence=["Source A: AANA makes constraints explicit."],
                    constraints=["Do not invent citations."],
                )
            ]
        )

        result = aana.check_batch(batch)

        self.assertEqual(result["summary"]["total"], 1)
        self.assertEqual(result["summary"]["failed"], 0)
        self.assertEqual(result["results"][0]["adapter"], "research_summary")

    def test_sdk_check_request_accepts_typed_request(self):
        request = aana.WorkflowRequest(
            adapter="research_summary",
            request="Write a concise research brief. Use only Source A and Source B. Label uncertainty.",
            candidate="AANA improves productivity by 40% for all teams [Source C].",
            evidence=[
                "Source A: AANA makes constraints explicit.",
                "Source B: Source coverage can be incomplete.",
            ],
            constraints=["Do not invent citations."],
            workflow_id="typed-workflow-001",
        )

        result = aana.check_request(request)

        self.assertEqual(result["workflow_id"], "typed-workflow-001")
        self.assertEqual(result["recommended_action"], "revise")

    def test_allowed_actions_are_enforced(self):
        result = aana.check(
            adapter="research_summary",
            request="Write a concise research brief. Use only Source A and Source B. Label uncertainty.",
            candidate="AANA improves productivity by 40% for all teams [Source C].",
            evidence=["Source A: AANA makes constraints explicit."],
            constraints=["Do not invent citations."],
            allowed_actions=["accept", "defer"],
        )

        self.assertEqual(result["recommended_action"], "defer")
        self.assertTrue(any(item["code"] == "recommended_action_not_allowed" for item in result["violations"]))
        self.assertEqual(result["aix"]["decision"], "revise")
        self.assertIn("recommended_action_not_allowed", result["aix"]["hard_blockers"])

    def test_schema_catalog_includes_workflow_schemas(self):
        schemas = aana.schema_catalog()

        self.assertIn("workflow_request", schemas)
        self.assertIn("workflow_batch_request", schemas)
        self.assertIn("workflow_result", schemas)
        self.assertIn("workflow_batch_result", schemas)
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

    def test_workflow_contract_accepts_structured_evidence_objects(self):
        workflow_request = workflow_contract.normalize_workflow_request(
            adapter="research_summary",
            request="Summarize Source A.",
            candidate="Unsupported answer [Source C].",
            evidence=[
                {
                    "source_id": "source-a",
                    "retrieved_at": "2026-05-05T00:00:00Z",
                    "trust_tier": "verified",
                    "redaction_status": "redacted",
                    "text": "Source A: AANA makes constraints explicit.",
                }
            ],
            constraints=["Use Source A only."],
            workflow_id="structured-evidence-001",
        )

        validation = workflow_contract.validate_workflow_request(workflow_request)
        event = workflow_contract.workflow_request_to_agent_event(workflow_request)
        result = aana.check_request(workflow_request)

        self.assertTrue(validation["valid"], validation)
        self.assertIn("source_id=source-a", event["available_evidence"][0])
        self.assertIn("trust_tier=verified", event["available_evidence"][0])
        self.assertEqual(result["workflow_id"], "structured-evidence-001")
        self.assertEqual(result["gate_decision"], "pass")

    def test_workflow_contract_rejects_malformed_evidence_objects(self):
        workflow_request = workflow_contract.normalize_workflow_request(
            adapter="research_summary",
            request="Summarize Source A.",
            evidence=[{"source_id": "source-a"}],
        )

        validation = workflow_contract.validate_workflow_request(workflow_request)

        self.assertFalse(validation["valid"])
        self.assertEqual(validation["issues"][0]["path"], "$.evidence")

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

    def test_http_workflow_batch_route(self):
        batch_request = agent_api.load_json_file(ROOT / "examples" / "workflow_batch_productive_work.json")

        status, payload = agent_server.route_request(
            "POST",
            "/workflow-batch",
            json.dumps(batch_request).encode("utf-8"),
        )

        self.assertEqual(status, 200)
        self.assertEqual(payload["summary"]["total"], 3)
        self.assertEqual(payload["summary"]["failed"], 0)
        self.assertEqual(payload["summary"]["recommended_actions"]["revise"], 3)

    def test_http_workflow_schema_route(self):
        status, payload = agent_server.route_request("GET", "/schemas/workflow-request.schema.json")

        self.assertEqual(status, 200)
        self.assertEqual(payload["title"], "AANA Workflow Request")
        self.assertIn("adapter", payload["properties"])

    def test_http_aix_schema_route(self):
        status, payload = agent_server.route_request("GET", "/schemas/aix.schema.json")

        self.assertEqual(status, 200)
        self.assertEqual(payload["title"], "AANA AIx Score")
        self.assertIn("score", payload["properties"])

    def test_sdk_workflow_audit_record_excludes_raw_text(self):
        workflow_request = agent_api.load_json_file(ROOT / "examples" / "workflow_research_summary.json")
        result = aana.check_request(workflow_request)

        record = aana.audit_workflow_check(
            workflow_request,
            result,
            created_at="2026-05-05T00:00:00+00:00",
        )
        serialized = str(record)

        self.assertEqual(record["record_type"], "workflow_check")
        self.assertEqual(record["adapter"], "research_summary")
        self.assertEqual(record["gate_decision"], "pass")
        self.assertEqual(record["recommended_action"], "revise")
        self.assertEqual(record["aix"]["decision"], "accept")
        self.assertGreater(record["violation_count"], 0)
        self.assertGreater(record["evidence_count"], 0)
        self.assertIn("sha256", record["input_fingerprints"]["request"])
        self.assertNotIn(workflow_request["request"], serialized)
        self.assertNotIn(workflow_request["candidate"], serialized)

    def test_sdk_workflow_batch_audit_record_summarizes_items(self):
        batch_request = agent_api.load_json_file(ROOT / "examples" / "workflow_batch_productive_work.json")
        result = aana.check_batch(batch_request)

        record = aana.audit_workflow_batch(
            batch_request,
            result,
            created_at="2026-05-05T00:00:00+00:00",
        )

        self.assertEqual(record["record_type"], "workflow_batch_check")
        self.assertEqual(record["batch_id"], "demo-batch-productive-work-001")
        self.assertEqual(record["summary"]["total"], 3)
        self.assertEqual(len(record["records"]), 3)
        self.assertTrue(all(item["record_type"] == "workflow_check" for item in record["records"]))


if __name__ == "__main__":
    unittest.main()
