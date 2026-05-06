import json
import pathlib
import unittest
from unittest import mock

import aana


ROOT = pathlib.Path(__file__).resolve().parents[1]


class AdapterIntegrationSdkTests(unittest.TestCase):
    def test_python_sdk_builds_structured_evidence_workflow_and_event(self):
        evidence = aana.normalize_evidence(
            "Source A: The claim is uncertain.",
            source_id="source-a",
            retrieved_at="2026-05-05T00:00:00Z",
            retrieval_url="aana://evidence/source-a",
        )
        workflow = aana.build_workflow_request(
            adapter="research_summary",
            request="Answer using Source A.",
            candidate="Unsupported claim [Source C].",
            evidence=evidence,
            constraints=["Use Source A only."],
            workflow_id="sdk-workflow-001",
        )
        event = aana.build_agent_event(
            adapter_id="research_summary",
            user_request="Answer using Source A.",
            candidate_action="Unsupported claim [Source C].",
            available_evidence=evidence,
            event_id="sdk-event-001",
        )

        self.assertEqual(evidence[0]["source_id"], "source-a")
        self.assertEqual(evidence[0]["redaction_status"], "redacted")
        self.assertEqual(evidence[0]["retrieval_url"], "aana://evidence/source-a")
        self.assertEqual(workflow["contract_version"], "0.1")
        self.assertEqual(workflow["workflow_id"], "sdk-workflow-001")
        self.assertEqual(event["event_version"], "0.1")
        self.assertEqual(event["event_id"], "sdk-event-001")

    def test_family_sdk_clients_attach_family_metadata_and_aliases(self):
        support = aana.SupportAANAClient()
        enterprise = aana.EnterpriseAANAClient()
        personal = aana.PersonalAANAClient()
        civic = aana.CivicAANAClient()

        support_workflow = support.workflow_request(
            adapter="crm",
            request="Draft a support reply.",
            candidate="Promise a refund without verified order facts.",
            evidence=[
                aana.evidence_object(
                    "Refund eligibility is unknown.",
                    source_id="support-policy",
                    retrieval_url="aana://evidence/support-policy",
                )
            ],
        )
        workflow = enterprise.workflow_request(
            adapter="deployment",
            request="Review deployment.",
            candidate="Ship now.",
            evidence=[aana.evidence_object("CI failed.", source_id="ci-result", retrieval_url="aana://evidence/ci-result")],
        )
        event = civic.agent_event(
            adapter_id="grant",
            user_request="Review application.",
            candidate_action="Guarantee award.",
            available_evidence=["Eligibility unknown."],
        )

        self.assertEqual(support_workflow["adapter"], "crm_support_reply")
        self.assertEqual(support_workflow["metadata"]["aana_family"], "support")
        self.assertEqual(support.resolve_adapter("email"), "email_send_guardrail")
        self.assertEqual(workflow["adapter"], "deployment_readiness")
        self.assertEqual(workflow["metadata"]["aana_family"], "enterprise")
        self.assertEqual(event["adapter_id"], "grant_application_review")
        self.assertEqual(event["metadata"]["aana_family"], "government_civic")
        self.assertEqual(personal.resolve_adapter("calendar"), "calendar_scheduling")

    def test_python_sdk_local_client_checks_workflow(self):
        client = aana.AANAClient()
        request = client.workflow_request(
            adapter="research_summary",
            request="Write a concise research brief. Use only Source A and Source B.",
            candidate="AANA improves productivity by 40% for all teams [Source C].",
            evidence=["Source A: AANA makes constraints explicit."],
            constraints=["Do not invent citations."],
        )

        result = client.workflow_check(request)

        self.assertEqual(result["gate_decision"], "pass")
        self.assertEqual(result["recommended_action"], "revise")

    def test_python_sdk_shadow_mode_observes_without_blocking(self):
        client = aana.AANAClient(shadow_mode=True)
        result = client.agent_check(
            adapter_id="support_reply",
            user_request="Draft a support reply with verified account facts.",
            candidate_action="Promise a refund and include private account details.",
            available_evidence=["Refund eligibility: unknown."],
        )

        self.assertEqual(result["execution_mode"], "shadow")
        self.assertEqual(result["production_decision"]["production_effect"], "not_blocked")
        self.assertEqual(result["shadow_observation"]["would_route"], "revise")

    def test_python_sdk_bridge_client_posts_contract_payloads(self):
        captured = {}

        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def read(self):
                return b'{"gate_decision":"pass","recommended_action":"accept"}'

        def fake_urlopen(request, timeout):
            captured["url"] = request.full_url
            captured["headers"] = dict(request.header_items())
            captured["body"] = json.loads(request.data.decode("utf-8"))
            captured["timeout"] = timeout
            return FakeResponse()

        client = aana.AANAClient(base_url="http://127.0.0.1:8765", token="secret", shadow_mode=True)
        workflow = client.workflow_request(
            adapter="research_summary",
            request="Answer using Source A.",
            candidate="Supported answer.",
        )

        with mock.patch("urllib.request.urlopen", side_effect=fake_urlopen):
            result = client.workflow_check(workflow)

        self.assertEqual(result["recommended_action"], "accept")
        self.assertIn("shadow_mode=true", captured["url"])
        self.assertEqual(captured["headers"]["Authorization"], "Bearer secret")
        self.assertEqual(captured["body"]["adapter"], "research_summary")
        self.assertEqual(captured["timeout"], 10.0)

    def test_typescript_sdk_package_contains_helpers(self):
        package_path = ROOT / "sdk" / "typescript" / "package.json"
        source_path = ROOT / "sdk" / "typescript" / "src" / "index.ts"
        readme_path = ROOT / "sdk" / "typescript" / "README.md"

        package = json.loads(package_path.read_text(encoding="utf-8"))
        source = source_path.read_text(encoding="utf-8")
        readme = readme_path.read_text(encoding="utf-8")

        self.assertEqual(package["name"], "@aana/integration-sdk")
        self.assertIn("export class AanaClient", source)
        self.assertIn("export class EnterpriseAANAClient", source)
        self.assertIn("export class SupportAANAClient", source)
        self.assertIn("export class PersonalAANAClient", source)
        self.assertIn("export class CivicAANAClient", source)
        self.assertIn("export function normalizeEvidence", source)
        self.assertIn("export function evidenceObject", source)
        self.assertIn("export function familyWorkflowRequest", source)
        self.assertIn("export function workflowRequest", source)
        self.assertIn("export function agentEvent", source)
        self.assertIn("shadowMode", source)
        self.assertIn("workflowCheck", readme)


if __name__ == "__main__":
    unittest.main()
