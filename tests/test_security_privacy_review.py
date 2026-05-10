import json
import tempfile
import unittest
from pathlib import Path

from eval_pipeline.human_review_queue import human_review_packet, validate_human_review_packet
from eval_pipeline.mi_audit import mi_audit_record, validate_mi_audit_record
from eval_pipeline.mi_observability import mi_dashboard_from_benchmark
from eval_pipeline.mi_pilot import run_research_citation_mi_pilot
from eval_pipeline.pilot_hardening import run_guarded_research_citation_pilot
from eval_pipeline.privacy_review import validate_redacted_artifact, validate_redacted_artifacts
from eval_pipeline.production_readiness import production_mi_readiness_gate
from scripts.validation.validate_mi_contracts import validate_dashboard, validate_production_readiness
from tests.test_handoff_gate import clean_handoff
from tests.test_human_review_queue import deferred_result


SECRET_CANARY = "sk-testsecret1234567890abcdef"
PRIVATE_RECORD_CANARY = "patient SSN 123-45-6789"
RAW_PROMPT_CANARY = "RAW_PROMPT: summarize the private customer record"
RAW_EVIDENCE_CANARY = "RAW_EVIDENCE: private source text"


def encoded(value):
    return json.dumps(value, sort_keys=True)


class SecurityPrivacyReviewTests(unittest.TestCase):
    def test_audit_record_never_stores_raw_prompt_private_record_or_evidence(self):
        handoff = clean_handoff()
        handoff["message"]["prompt"] = RAW_PROMPT_CANARY
        handoff["message"]["private_record"] = PRIVATE_RECORD_CANARY
        handoff["message"]["claims"] = [SECRET_CANARY]
        handoff["evidence"][0]["text"] = RAW_EVIDENCE_CANARY
        pilot_result = run_research_citation_mi_pilot()
        result = pilot_result["mi_batch"]["results"][0]
        result["message"] = handoff["message"]
        result["evidence"] = handoff["evidence"]

        record = mi_audit_record(result, created_at="2026-05-06T00:00:00Z", workflow_id="wf-private")
        record_text = encoded(record)

        self.assertNotIn(RAW_PROMPT_CANARY, record_text)
        self.assertNotIn(PRIVATE_RECORD_CANARY, record_text)
        self.assertNotIn(SECRET_CANARY, record_text)
        self.assertNotIn(RAW_EVIDENCE_CANARY, record_text)
        self.assertTrue(validate_mi_audit_record(record)["valid"])
        self.assertTrue(validate_redacted_artifact(record)["valid"])

    def test_audit_validator_rejects_nested_raw_fields_and_secrets(self):
        record = mi_audit_record(run_research_citation_mi_pilot()["mi_batch"]["results"][0])
        record["metadata"] = {"raw_prompt": RAW_PROMPT_CANARY}
        record["aix"]["secret"] = SECRET_CANARY

        report = validate_mi_audit_record(record)

        self.assertFalse(report["valid"])
        self.assertTrue(any(issue["path"] == "$.metadata.raw_prompt" for issue in report["issues"]))
        self.assertTrue(any("openai_api_key" in issue["message"] for issue in report["issues"]))

    def test_human_review_packet_redacts_raw_prompt_private_records_and_evidence(self):
        result = deferred_result()
        result["message"]["raw_prompt"] = RAW_PROMPT_CANARY
        result["message"]["private_record"] = PRIVATE_RECORD_CANARY
        result["evidence"][0]["text"] = RAW_EVIDENCE_CANARY
        result["message"]["claims"] = [SECRET_CANARY]

        packet = human_review_packet(result)
        packet_text = encoded(packet)

        self.assertNotIn(RAW_PROMPT_CANARY, packet_text)
        self.assertNotIn(PRIVATE_RECORD_CANARY, packet_text)
        self.assertNotIn(SECRET_CANARY, packet_text)
        self.assertNotIn(RAW_EVIDENCE_CANARY, packet_text)
        self.assertTrue(validate_human_review_packet(packet)["valid"])

    def test_human_review_validator_rejects_leaked_private_fields(self):
        packet = human_review_packet(deferred_result())
        packet["review_context"] = {"private_records": [PRIVATE_RECORD_CANARY]}

        report = validate_human_review_packet(packet)

        self.assertFalse(report["valid"])
        self.assertTrue(any(issue["path"] == "$.review_context.private_records" for issue in report["issues"]))
        self.assertTrue(any("ssn" in issue["message"] for issue in report["issues"]))

    def test_dashboard_and_readiness_artifacts_pass_redaction_review(self):
        pilot = run_research_citation_mi_pilot()
        dashboard = mi_dashboard_from_benchmark(
            {
                "workflows": [
                    {
                        "workflow_id": pilot["workflow_id"],
                        "expected_issue": "unsupported_research_citation",
                        "expected_detection": True,
                        "modes": [
                            {
                                "mode": "full_global_aana_gate",
                                "detected": True,
                                "signals": {"revise_upstream_output": 1},
                                "handoff_total": 3,
                                "handoff_blocked": 1,
                                "gate_decisions": {"pass": 2, "block": 1},
                                "recommended_actions": {"accept": 2, "revise": 1},
                                "propagated_risk_count": 1,
                                "shared_correction_action_count": 1,
                            }
                        ],
                    }
                ]
            }
        )
        readiness = production_mi_readiness_gate(pilot)

        report = validate_redacted_artifacts({"dashboard": dashboard, "readiness": readiness})

        self.assertTrue(report["valid"], report["issues"])
        self.assertNotIn("AANA verifier loops improve productivity by 40%", encoded(dashboard))
        self.assertNotIn("AANA verifier loops improve productivity by 40%", encoded(readiness))

    def test_contract_validator_fails_on_dashboard_or_readiness_privacy_leakage(self):
        dashboard = mi_dashboard_from_benchmark({"workflows": []})
        dashboard["workflow_rows"].append({"workflow_id": "wf-1", "raw_prompt": RAW_PROMPT_CANARY})
        readiness = production_mi_readiness_gate(run_research_citation_mi_pilot())
        readiness["checklist"][0]["details"] = SECRET_CANARY

        with tempfile.TemporaryDirectory() as directory:
            dashboard_path = Path(directory) / "mi_dashboard.json"
            readiness_path = Path(directory) / "production_mi_readiness.json"
            dashboard_path.write_text(json.dumps(dashboard), encoding="utf-8")
            readiness_path.write_text(json.dumps(readiness), encoding="utf-8")

            dashboard_issues = validate_dashboard(dashboard_path)
            readiness_issues = validate_production_readiness(readiness_path)

        self.assertTrue(any("Raw private content field" in issue.message for issue in dashboard_issues))
        self.assertTrue(any("openai_api_key" in issue.message for issue in readiness_issues))

    def test_guarded_live_human_review_artifact_is_redacted(self):
        result = run_guarded_research_citation_pilot(allow_direct_execution=True)
        queue = result["human_review_queue"]

        self.assertGreaterEqual(queue["packet_count"], 1)
        self.assertTrue(queue["validation"]["valid"], queue["validation"]["issues"])
        self.assertTrue(validate_redacted_artifact(queue["packets"])["valid"])


if __name__ == "__main__":
    unittest.main()
