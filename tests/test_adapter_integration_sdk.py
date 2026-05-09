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

    def test_python_sdk_builds_and_checks_tool_precheck_event(self):
        event = aana.build_tool_precheck_event(
            request_id="tool-sdk-001",
            agent_id="test-agent",
            tool_name="get_recent_transactions",
            tool_category="private_read",
            authorization_state="authenticated",
            evidence_refs=[
                aana.tool_evidence_ref(
                    source_id="auth.email.lookup",
                    kind="auth_event",
                    trust_tier="verified",
                    redaction_status="redacted",
                    summary="User was authenticated through an email lookup.",
                )
            ],
            risk_domain="finance",
            proposed_arguments={"account_id": "acct_redacted", "limit": 10},
            recommended_route="accept",
        )

        validation = aana.validate_tool_precheck_event(event)
        result = aana.check_tool_precheck(event)
        decision = aana.check_tool_call(event)

        self.assertEqual(validation, [])
        self.assertEqual(event["schema_version"], aana.TOOL_PRECHECK_SCHEMA_VERSION)
        self.assertEqual(result["gate_decision"], "pass")
        self.assertEqual(decision["architecture_decision"]["route"], "accept")
        self.assertEqual(decision["architecture_decision"]["authorization_state"], "authenticated")
        self.assertEqual(decision["architecture_decision"]["evidence_refs"]["used"], ["auth.email.lookup"])
        self.assertTrue(aana.should_execute_tool(result))

    def test_python_sdk_gate_action_alias_returns_architecture_decision(self):
        result = aana.gate_action(
            tool_name="send_refund",
            tool_category="write",
            authorization_state="validated",
            evidence_refs=[
                aana.tool_evidence_ref(
                    source_id="policy.refund",
                    kind="policy",
                    trust_tier="verified",
                    redaction_status="public",
                    summary="Refund policy is present, but confirmation is missing.",
                )
            ],
            risk_domain="commerce",
            proposed_arguments={"order_id": "order_redacted"},
            recommended_route="accept",
        )

        self.assertEqual(result["recommended_action"], "ask")
        self.assertEqual(result["architecture_decision"]["route"], "ask")
        self.assertIn("write_missing_explicit_confirmation", result["architecture_decision"]["hard_blockers"])
        self.assertIn("Ask the user", result["architecture_decision"]["correction_recovery_suggestion"])

    def test_public_agent_action_quickstart_shape_asks_for_confirmation(self):
        decision = aana.check_tool_call(
            {
                "tool_name": "send_email",
                "tool_category": "write",
                "authorization_state": "user_claimed",
                "evidence_refs": ["draft_id:123"],
                "risk_domain": "customer_support",
                "proposed_arguments": {"to": "customer@example.com"},
                "recommended_route": "accept",
            }
        )

        self.assertEqual(decision["recommended_action"], "ask")
        self.assertEqual(decision["architecture_decision"]["route"], "ask")
        self.assertEqual(decision["architecture_decision"]["evidence_refs"]["used"], ["draft_id:123"])
        self.assertIn("write_missing_validation_or_confirmation", decision["architecture_decision"]["hard_blockers"])
        self.assertIn("Ask the user", decision["architecture_decision"]["correction_recovery_suggestion"])
        audit_event = decision["architecture_decision"]["audit_safe_log_event"]
        self.assertEqual(audit_event["audit_event_version"], "aana.audit_safe_decision.v1")
        self.assertEqual(audit_event["route"], "ask")
        self.assertEqual(audit_event["aix_score"], decision["aix"]["score"])
        self.assertIn("write_missing_validation_or_confirmation", audit_event["hard_blockers"])
        self.assertIn("write_missing_validation_or_confirmation", audit_event["missing_evidence"])
        self.assertEqual(audit_event["authorization_state"], "user_claimed")
        self.assertIn("latency_ms", audit_event)
        self.assertFalse(audit_event["raw_payload_logged"])

    def test_public_agent_action_quickstart_shape_accepts_confirmed_write(self):
        decision = aana.check_tool_call(
            {
                "tool_name": "send_email",
                "tool_category": "write",
                "authorization_state": "confirmed",
                "evidence_refs": ["draft_id:123", "approval:user-confirmed-send"],
                "risk_domain": "customer_support",
                "proposed_arguments": {"to": "customer@example.com"},
                "recommended_route": "accept",
            }
        )

        self.assertEqual(decision["recommended_action"], "accept")
        self.assertTrue(aana.should_execute_tool(decision))
        self.assertEqual(decision["architecture_decision"]["route"], "accept")

    def test_python_sdk_tool_precheck_blocks_missing_authorization_evidence(self):
        client = aana.AANAClient()
        result = client.tool_precheck(
            tool_name="find_account_key_by_email",
            tool_category="public_read",
            authorization_state="none",
            evidence_refs=[
                aana.tool_evidence_ref(
                    source_id="counterfactual.missing_authorization",
                    kind="system_state",
                    trust_tier="verified",
                    redaction_status="public",
                    summary="Counterfactual stressor removes verified authorization context.",
                )
            ],
            risk_domain="finance",
            proposed_arguments={"email": "redacted@example.com"},
            recommended_route="accept",
        )

        self.assertEqual(result["recommended_action"], "defer")
        self.assertEqual(result["gate_decision"], "fail")
        self.assertEqual(result["architecture_decision"]["route"], "defer")
        self.assertIn("audit_safe_log_event", result["architecture_decision"])
        self.assertFalse(aana.should_execute_tool(result))

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

    def test_python_sdk_bridge_client_posts_tool_precheck_payloads(self):
        captured = {}

        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def read(self):
                return b'{"gate_decision":"pass","recommended_action":"accept","hard_blockers":[]}'

        def fake_urlopen(request, timeout):
            captured["url"] = request.full_url
            captured["body"] = json.loads(request.data.decode("utf-8"))
            captured["timeout"] = timeout
            return FakeResponse()

        client = aana.AANAClient(base_url="http://127.0.0.1:8765", shadow_mode=True)
        event = client.tool_precheck_event(
            tool_name="get_game_score",
            tool_category="public_read",
            authorization_state="none",
            evidence_refs=[aana.tool_evidence_ref(source_id="policy.public_scores", kind="policy")],
            risk_domain="public_information",
            proposed_arguments={"game_id": "GAME-123"},
            recommended_route="accept",
        )

        with mock.patch("urllib.request.urlopen", side_effect=fake_urlopen):
            result = client.tool_precheck(event)

        self.assertEqual(result["recommended_action"], "accept")
        self.assertIn("/tool-precheck", captured["url"])
        self.assertIn("shadow_mode=true", captured["url"])
        self.assertEqual(captured["body"]["schema_version"], "aana.agent_tool_precheck.v1")
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
        self.assertIn("export function toolPrecheckEvent", source)
        self.assertIn("export function checkToolPrecheck", source)
        self.assertIn("export function shouldExecuteTool", source)
        self.assertIn("shadowMode", source)
        self.assertIn("workflowCheck", readme)
        self.assertIn("toolPrecheck", readme)


if __name__ == "__main__":
    unittest.main()
