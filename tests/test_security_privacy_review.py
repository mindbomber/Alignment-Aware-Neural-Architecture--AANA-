import importlib.util
import json
import pathlib
import unittest

from eval_pipeline import agent_api, agent_server


ROOT = pathlib.Path(__file__).resolve().parents[1]
REVIEW_PATH = ROOT / "examples" / "security_privacy_review_support.json"
FIXTURE_PATH = ROOT / "examples" / "support_workflow_contract_examples.json"


def load_script(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


security_review = load_script("validate_security_privacy_review", ROOT / "scripts" / "validate_security_privacy_review.py")


def _review():
    return json.loads(REVIEW_PATH.read_text(encoding="utf-8"))


def _fixture_case(name):
    payload = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    for case in payload["cases"]:
        if case["name"] == name:
            return case
    raise AssertionError(f"missing support fixture {name}")


def _raw_forbidden_terms(case):
    workflow = case["workflow_request"]
    terms = [
        workflow["request"],
        workflow["candidate"],
        case["agent_event"]["user_request"],
        case["agent_event"]["candidate_action"],
        case["candidate_output"],
        case["candidate_bad_output"],
    ]
    terms.extend(item["text"] for item in workflow["evidence"])
    terms.extend(case["agent_event"]["available_evidence"])
    return [term for term in terms if isinstance(term, str) and term]


class SecurityPrivacyReviewTests(unittest.TestCase):
    def test_review_manifest_covers_required_controls(self):
        report = security_review.validate_review(REVIEW_PATH)

        self.assertTrue(report["valid"], report)
        self.assertEqual(set(report["required_controls"]), security_review.REQUIRED_CONTROLS)
        self.assertEqual(report["control_count"], len(security_review.REQUIRED_CONTROLS))

    def test_review_manifest_declares_external_deployment_blockers(self):
        review = _review()

        self.assertEqual(review["deployment_position"]["repo_local_status"], "demo-ready/pilot-ready/production-candidate")
        self.assertEqual(review["deployment_position"]["production_status"], "not production-certified by local tests alone")
        blockers = set(review["deployment_position"]["production_blockers"])
        self.assertIn("live evidence connector permission review", blockers)
        self.assertIn("domain owner signoff", blockers)
        self.assertIn("audit retention policy approval", blockers)
        self.assertIn("observability approval", blockers)
        self.assertIn("human review staffing and SLA", blockers)
        self.assertIn("security review approval", blockers)
        self.assertIn("deployment manifest approval", blockers)
        self.assertIn("incident response plan approval", blockers)
        self.assertIn("measured pilot results", blockers)
        self.assertIn("rate limit and abuse plan approved by deployment owner", blockers)

        controls = {control["id"]: control for control in review["controls"]}
        self.assertEqual(controls["evidence_connector_permission_review"]["status"], "external_required")
        self.assertEqual(controls["audit_retention_policy"]["status"], "external_required")
        self.assertEqual(controls["secrets_scanning"]["status"], "plan_required")

    def test_support_audit_omits_raw_prompt_candidate_and_evidence(self):
        case = _fixture_case("draft_refund_missing_account_facts")
        workflow_request = case["workflow_request"]
        result = agent_api.check_workflow_request(workflow_request)
        record = agent_api.audit_workflow_check(workflow_request, result, created_at="2026-05-05T12:00:00+00:00")

        serialized = json.dumps(record, sort_keys=True)
        for term in _raw_forbidden_terms(case):
            self.assertNotIn(term, serialized)
        redaction = agent_api.audit_redaction_report([record], forbidden_terms=_raw_forbidden_terms(case))
        self.assertTrue(redaction["redacted"], redaction)

        self.assertEqual(record["adapter_id"], "crm_support_reply")
        self.assertEqual(record["violation_codes"], sorted(case["expected"]["workflow"]["violation_codes"]))
        self.assertIn("sha256", record["input_fingerprints"]["request"])
        self.assertIn("sha256", record["input_fingerprints"]["candidate"])

    def test_internal_crm_note_case_blocks_and_audits_metadata_only(self):
        case = _fixture_case("block_internal_crm_note_leakage")
        workflow_request = case["workflow_request"]
        result = agent_api.check_workflow_request(workflow_request)
        record = agent_api.audit_workflow_check(workflow_request, result, created_at="2026-05-05T12:00:00+00:00")

        self.assertEqual(result["candidate_gate"], "block")
        self.assertIn("internal_crm_detail", {item["code"] for item in result["violations"]})
        self.assertIn("bypass_verification", {item["code"] for item in result["violations"]})
        self.assertEqual(record["human_review_queue"]["queue"], "support_human_review")
        self.assertIn("internal_fraud_risk_note_exposure", record["human_review_queue"]["triggers"])
        self.assertTrue(agent_api.audit_redaction_report([record], forbidden_terms=_raw_forbidden_terms(case))["redacted"])

    def test_attachment_private_export_case_blocks_and_audits_metadata_only(self):
        case = _fixture_case("block_private_export_attachment")
        workflow_request = case["workflow_request"]
        result = agent_api.check_workflow_request(workflow_request)
        record = agent_api.audit_workflow_check(workflow_request, result, created_at="2026-05-05T12:00:00+00:00")

        violation_codes = {item["code"] for item in result["violations"]}
        self.assertEqual(result["candidate_gate"], "block")
        self.assertIn("unsafe_email_attachment", violation_codes)
        self.assertIn("private_email_data", violation_codes)
        self.assertEqual(record["adapter_id"], "email_send_guardrail")
        self.assertTrue(agent_api.audit_redaction_report([record], forbidden_terms=_raw_forbidden_terms(case))["redacted"])

    def test_bridge_security_controls_do_not_expose_tokens(self):
        config = agent_server.bridge_config(auth_token="secret-token", rate_limit_per_minute=5)
        redacted = agent_server._redact_log_text(
            "Authorization: Bearer secret-token X-AANA-Token: secret-token token=secret-token"
        )

        self.assertTrue(config["auth_required"])
        self.assertEqual(config["auth_token_source"], "value")
        self.assertEqual(config["raw_debug_leakage"], "disabled")
        self.assertTrue(config["redacted_logs"])
        self.assertNotIn("secret-token", json.dumps(config, sort_keys=True))
        self.assertNotIn("secret-token", redacted)
        self.assertIn("[redacted]", redacted)

    def test_bridge_rate_limit_control_blocks_after_limit(self):
        event = agent_api.load_json_file(ROOT / "examples" / "agent_event_support_reply.json")
        state = {}

        first_status, _ = agent_server.route_request(
            "POST",
            "/validate-event",
            json.dumps(event).encode("utf-8"),
            rate_limit_per_minute=1,
            rate_limit_state=state,
            client_id="support-client",
        )
        second_status, second_payload = agent_server.route_request(
            "POST",
            "/validate-event",
            json.dumps(event).encode("utf-8"),
            rate_limit_per_minute=1,
            rate_limit_state=state,
            client_id="support-client",
        )

        self.assertEqual(first_status, 200)
        self.assertEqual(second_status, 429)
        self.assertEqual(second_payload["error_code"], "rate_limited")


if __name__ == "__main__":
    unittest.main()
