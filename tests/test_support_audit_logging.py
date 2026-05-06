import json
import pathlib
import unittest

from eval_pipeline import agent_api


ROOT = pathlib.Path(__file__).resolve().parents[1]
FIXTURE_PATH = ROOT / "examples" / "support_workflow_contract_examples.json"
CREATED_AT = "2026-05-05T12:00:00+00:00"


def _fixture_cases():
    payload = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    return payload["cases"]


def _raw_forbidden_terms(case):
    terms = [
        case["workflow_request"]["request"],
        case["workflow_request"]["candidate"],
        case["agent_event"]["user_request"],
        case["agent_event"]["candidate_action"],
        case["candidate_output"],
        case["candidate_bad_output"],
    ]
    terms.extend(item["text"] for item in case["workflow_request"]["evidence"])
    terms.extend(case["agent_event"]["available_evidence"])
    return [term for term in terms if isinstance(term, str) and term]


class SupportAuditLoggingTests(unittest.TestCase):
    def test_workflow_audit_records_preserve_only_metadata_and_fingerprints(self):
        records = []
        for case in _fixture_cases():
            with self.subTest(case=case["name"]):
                workflow_request = case["workflow_request"]
                result = agent_api.check_workflow_request(workflow_request)
                record = agent_api.audit_workflow_check(workflow_request, result, created_at=CREATED_AT)
                records.append(record)

                self.assertEqual(record["record_type"], "workflow_check")
                self.assertEqual(record["adapter_id"], workflow_request["adapter"])
                self.assertEqual(record["workflow_id"], workflow_request["workflow_id"])
                self.assertEqual(record["gate_decision"], result["gate_decision"])
                self.assertEqual(record["recommended_action"], result["recommended_action"])
                self.assertEqual(record["violation_codes"], sorted({item["code"] for item in result.get("violations", [])}))
                self.assertEqual(record["hard_blockers"], result.get("aix", {}).get("hard_blockers", []))
                self.assertEqual(
                    record["evidence_source_ids"],
                    [item["source_id"] for item in workflow_request["evidence"]],
                )
                self.assertEqual(record["created_at"], CREATED_AT)
                self.assertEqual(record["execution_mode"], "enforce")
                self.assertIn("sha256", record["input_fingerprints"]["request"])
                self.assertIn("sha256", record["input_fingerprints"]["candidate"])
                self.assertEqual(len(record["input_fingerprints"]["evidence"]), len(workflow_request["evidence"]))
                self.assertIsInstance(record["aix"]["score"], (int, float))
                self.assertIsInstance(record["aix"]["decision"], str)
                self.assertIsInstance(record["aix"]["components"], dict)
                self.assertIsInstance(record["human_review_route"]["required"], bool)
                self.assertIsInstance(record["human_review_route"]["route"], str)
                self.assertIsInstance(record["human_review_queue"]["required"], bool)
                self.assertIsInstance(record["human_review_queue"]["queue"], str)
                self.assertIsInstance(record["human_review_queue"]["triggers"], list)
                if record["human_review_queue"]["required"]:
                    self.assertEqual(record["human_review_queue"]["queue"], "support_human_review")

                report = agent_api.validate_audit_records([record])
                self.assertTrue(report["valid"], report)
                redaction = agent_api.audit_redaction_report([record], forbidden_terms=_raw_forbidden_terms(case))
                self.assertTrue(redaction["redacted"], redaction)

        report = agent_api.validate_audit_records(records)
        self.assertTrue(report["valid"], report)

    def test_agent_event_audit_records_extract_metadata_from_event_evidence(self):
        for case in _fixture_cases():
            with self.subTest(case=case["name"]):
                event = case["agent_event"]
                result = agent_api.check_event(event)
                record = agent_api.audit_event_check(event, result, created_at=CREATED_AT)

                self.assertEqual(record["record_type"], "agent_check")
                self.assertEqual(record["adapter_id"], event["adapter_id"])
                self.assertEqual(record["event_id"], event["event_id"])
                self.assertEqual(record["gate_decision"], result["gate_decision"])
                self.assertEqual(record["recommended_action"], result["recommended_action"])
                self.assertEqual(record["violation_codes"], sorted({item["code"] for item in result.get("violations", [])}))
                self.assertEqual(record["created_at"], CREATED_AT)
                self.assertEqual(record["execution_mode"], "enforce")
                self.assertEqual(
                    record["evidence_source_ids"],
                    [item["source_id"] for item in case["workflow_request"]["evidence"]],
                )
                self.assertIn("sha256", record["input_fingerprints"]["user_request"])
                self.assertIn("sha256", record["input_fingerprints"]["candidate"])
                self.assertIn("human_review_queue", record)

                report = agent_api.validate_audit_records([record])
                self.assertTrue(report["valid"], report)
                redaction = agent_api.audit_redaction_report([record], forbidden_terms=_raw_forbidden_terms(case))
                self.assertTrue(redaction["redacted"], redaction)

    def test_support_human_review_queue_covers_required_triggers(self):
        cases = [
            ("unsupported_refund_promise", "revise", [], {"refund_exception", "policy_ambiguity"}),
            ("private_payment_data", "revise", [], {"payment_billing_data_exposure"}),
            ("internal_crm_detail", "revise", [], {"internal_fraud_risk_note_exposure"}),
            ("legal_jurisdiction_unverified", "defer", [], {"legal_regulatory_request", "recommended_action_defer"}),
            ("account_deletion_request", "defer", [], {"account_closure_deletion_request", "recommended_action_defer"}),
            ("missing_account_verification_path", "ask", [], {"identity_uncertainty"}),
            ("high_value_customer_escalation", "defer", [], {"high_value_customer_escalation", "recommended_action_defer"}),
            ("policy_ambiguity", "ask", [], {"policy_ambiguity"}),
            ("clean_candidate", "accept", ["aix_blocked"], {"aix_hard_blocker"}),
            ("defer_without_violation", "defer", [], {"recommended_action_defer"}),
        ]
        workflow_request = {
            "contract_version": "0.1",
            "workflow_id": "support-human-review-trigger-test",
            "adapter": "crm_support_reply",
            "request": "metadata-only support audit trigger test",
            "candidate": "metadata-only candidate",
            "evidence": [{"source_id": "support-policy", "text": "redacted policy fixture"}],
            "allowed_actions": ["accept", "revise", "retrieve", "ask", "defer", "refuse"],
        }

        for code, action, hard_blockers, expected_triggers in cases:
            with self.subTest(code=code, action=action):
                violations = [] if code in {"clean_candidate", "defer_without_violation"} else [{"code": code, "severity": "critical"}]
                result = {
                    "contract_version": "0.1",
                    "workflow_id": workflow_request["workflow_id"],
                    "adapter": workflow_request["adapter"],
                    "gate_decision": "pass",
                    "recommended_action": action,
                    "candidate_gate": "block" if violations or hard_blockers else "pass",
                    "violations": violations,
                    "aix": {
                        "score": 0.5 if violations or hard_blockers else 1.0,
                        "decision": action,
                        "components": {},
                        "hard_blockers": hard_blockers,
                    },
                    "output": None,
                }
                record = agent_api.audit_workflow_check(workflow_request, result, created_at=CREATED_AT)
                queue = record["human_review_queue"]

                self.assertTrue(queue["required"])
                self.assertEqual(queue["queue"], "support_human_review")
                self.assertTrue(expected_triggers.issubset(set(queue["triggers"])), queue)
                self.assertIn(queue["priority"], {"high", "critical"})

                report = agent_api.validate_audit_records([record])
                self.assertTrue(report["valid"], report)

    def test_human_review_queue_metrics_are_exported(self):
        records = []
        for case in _fixture_cases():
            workflow_request = case["workflow_request"]
            result = agent_api.check_workflow_request(workflow_request)
            records.append(agent_api.audit_workflow_check(workflow_request, result, created_at=CREATED_AT))

        metrics = agent_api.export_audit_metrics(records, created_at=CREATED_AT)

        self.assertGreater(metrics["metrics"]["human_review_queue_count"], 0)
        self.assertGreater(metrics["metrics"]["human_review_trigger_count"], 0)
        self.assertIn("human_review_triggers", metrics["summary"])
        validation = agent_api.validate_audit_metrics_export(metrics)
        self.assertTrue(validation["valid"], validation)

    def test_operational_observability_metrics_are_exported(self):
        workflow_request = {
            "contract_version": "0.1",
            "workflow_id": "support-observability-test",
            "adapter": "crm_support_reply",
            "request": "metadata-only observability test",
            "candidate": "metadata-only candidate",
            "evidence": [
                {
                    "source_id": "crm-record",
                    "text": "redacted fixture",
                    "connector_status": "failed",
                    "freshness_status": "stale",
                }
            ],
            "allowed_actions": ["accept", "revise", "retrieve", "ask", "defer", "refuse"],
        }
        base_result = {
            "contract_version": "0.1",
            "workflow_id": workflow_request["workflow_id"],
            "adapter": workflow_request["adapter"],
            "gate_decision": "pass",
            "recommended_action": "accept",
            "violations": [],
            "aix": {
                "score": 0.96,
                "decision": "accept",
                "components": {},
                "hard_blockers": [],
            },
            "audit_metadata": {
                "adapter_version": "2026.05.01",
                "latency_ms": 42.5,
                "connector_failures": [{"connector_id": "support-policy", "code": "timeout"}],
                "evidence_freshness_failures": [{"source_id": "order-system", "code": "stale_evidence"}],
            },
            "output": None,
        }
        second_result = dict(base_result)
        second_result["audit_metadata"] = dict(base_result["audit_metadata"], adapter_version="2026.05.02", latency_ms=1200)
        second_result["recommended_action"] = "defer"
        second_result["aix"] = dict(base_result["aix"], score=0.62, decision="defer", hard_blockers=["stale_evidence"])

        records = [
            agent_api.audit_workflow_check(workflow_request, base_result, created_at=CREATED_AT),
            agent_api.audit_workflow_check(workflow_request, second_result, created_at=CREATED_AT),
        ]
        metrics = agent_api.export_audit_metrics(records, created_at=CREATED_AT)
        dashboard = agent_api.audit_dashboard(records, created_at=CREATED_AT)

        self.assertEqual(metrics["metrics"]["adapter_check_count.crm_support_reply"], 2)
        self.assertEqual(metrics["metrics"]["connector_failure_count"], 4)
        self.assertEqual(metrics["metrics"]["evidence_freshness_failure_count"], 4)
        self.assertEqual(metrics["metrics"]["drift_by_adapter_version_count"], 1)
        self.assertEqual(metrics["metrics"]["adapter_version_distinct_count.crm_support_reply"], 2)
        self.assertEqual(metrics["metrics"]["latency_count"], 2)
        self.assertEqual(metrics["metrics"]["latency_bucket_count.gt_1000ms"], 1)
        self.assertEqual(metrics["metrics"]["aix_score_bucket_count.gte_0_95"], 1)
        self.assertEqual(metrics["metrics"]["aix_score_bucket_count.gte_0_50_lt_0_70"], 1)
        self.assertEqual(metrics["metrics"]["refusal_defer_rate"], 0.5)
        self.assertEqual(metrics["metrics"]["defer_rate"], 0.5)
        self.assertEqual(dashboard["cards"]["connector_failure_total"], 4)
        self.assertEqual(dashboard["cards"]["evidence_freshness_failure_total"], 4)
        self.assertEqual(dashboard["cards"]["adapter_version_drift"], 1)
        self.assertTrue(dashboard["adapter_breakdown"][0]["adapter_version_drift"])

        validation = agent_api.validate_audit_metrics_export(metrics)
        self.assertTrue(validation["valid"], validation)


if __name__ == "__main__":
    unittest.main()
