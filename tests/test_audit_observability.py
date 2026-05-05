import pathlib
import tempfile
import unittest

from eval_pipeline import agent_api


def sample_record(**overrides):
    record = {
        "audit_record_version": "0.1",
        "created_at": "2026-05-05T00:00:00+00:00",
        "record_type": "agent_check",
        "event_version": "0.1",
        "event_id": "evt-001",
        "agent": "test-agent",
        "adapter_id": "support_reply",
        "workflow": "Support Reply",
        "gate_decision": "pass",
        "recommended_action": "revise",
        "candidate_gate": "block",
        "aix": {
            "score": 0.91,
            "decision": "revise",
            "components": {"P": 1.0, "B": 0.85, "C": 0.9},
            "beta": 1.2,
            "thresholds": {"accept": 0.9, "revise": 0.7, "defer": 0.5},
            "hard_blockers": [],
        },
        "violation_count": 1,
        "violation_codes": ["unsupported_claim"],
        "violation_severities": {"medium": 1},
        "allowed_actions": ["accept", "revise", "ask", "defer", "refuse"],
        "input_fingerprints": {
            "user_request": {"sha256": "a" * 64, "length": 12},
            "candidate": {"sha256": "b" * 64, "length": 18},
            "evidence": [{"sha256": "c" * 64, "length": 8}],
            "safe_response": {"sha256": "d" * 64, "length": 24},
        },
    }
    record.update(overrides)
    return record


class AuditObservabilityTests(unittest.TestCase):
    def test_audit_record_schema_validation_accepts_redacted_record(self):
        report = agent_api.validate_audit_records([sample_record()])

        self.assertTrue(report["valid"], report)
        self.assertEqual(report["record_count"], 1)

    def test_audit_record_schema_validation_rejects_raw_fields(self):
        report = agent_api.validate_audit_records(
            [
                sample_record(
                    candidate="Customer card ending 4242 should receive refund.",
                    available_evidence=["raw CRM note"],
                )
            ]
        )

        self.assertFalse(report["valid"])
        paths = {issue["path"] for issue in report["issues"]}
        self.assertIn("$[0].candidate", paths)
        self.assertIn("$[0].available_evidence", paths)

    def test_redaction_report_rejects_forbidden_terms(self):
        report = agent_api.audit_redaction_report(
            [sample_record()],
            forbidden_terms=["support_reply", "card ending 4242"],
        )

        self.assertFalse(report["valid"])
        self.assertTrue(any("support_reply" in issue["message"] for issue in report["issues"]))

    def test_metrics_export_golden_fields(self):
        payload = agent_api.export_audit_metrics(
            [sample_record()],
            audit_log_path="audit.jsonl",
            created_at="2026-05-05T00:01:00+00:00",
        )
        validation = agent_api.validate_audit_metrics_export(payload)

        self.assertTrue(validation["valid"], validation)
        self.assertEqual(payload["audit_metrics_export_version"], "0.1")
        self.assertEqual(payload["record_count"], 1)
        self.assertEqual(payload["metrics"]["audit_records_total"], 1)
        self.assertEqual(payload["metrics"]["gate_decision_count.pass"], 1)
        self.assertEqual(payload["metrics"]["recommended_action_count.revise"], 1)
        self.assertEqual(payload["metrics"]["shadow_records_total"], 0)
        self.assertEqual(payload["metrics"]["shadow_would_action_count"], 0)
        self.assertEqual(payload["metrics"]["shadow_would_pass_count"], 0)
        self.assertEqual(payload["metrics"]["shadow_would_revise_count"], 0)
        self.assertEqual(payload["metrics"]["shadow_would_defer_count"], 0)
        self.assertEqual(payload["metrics"]["shadow_would_refuse_count"], 0)
        self.assertEqual(payload["metrics"]["adapter_check_count.support_reply"], 1)
        self.assertEqual(payload["metrics"]["family_check_count.enterprise"], 1)
        self.assertEqual(payload["metrics"]["role_check_count.support"], 1)
        self.assertEqual(payload["metrics"]["violation_code_count.unsupported_claim"], 1)
        self.assertEqual(payload["metrics"]["aix_score_average"], 0.91)
        self.assertEqual(payload["metrics"]["aix_decision_count.revise"], 1)
        self.assertEqual(payload["metrics"]["aix_hard_blocker_count"], 0)

    def test_dashboard_payload_includes_reviewer_metrics(self):
        shadow = sample_record(
            created_at="2026-05-06T00:00:00+00:00",
            adapter_id="email_send_guardrail",
            recommended_action="defer",
            aix={
                "score": 0.52,
                "decision": "defer",
                "components": {"P": 0.7, "B": 0.45, "C": 0.55},
                "beta": 1.6,
                "thresholds": {"accept": 0.95},
                "hard_blockers": ["missing_user_approval"],
            },
            execution_mode="shadow",
            shadow_observation={
                "shadow_mode": True,
                "enforcement": "observe_only",
                "would_gate_decision": "pass",
                "would_recommended_action": "defer",
                "would_candidate_gate": "block",
                "would_aix_decision": "defer",
                "would_route": "defer",
                "production_effect": "not_blocked",
            },
            violation_count=2,
            violation_codes=["missing_approval", "irreversible_send_risk"],
        )

        payload = agent_api.audit_dashboard(
            [sample_record(), shadow],
            audit_log_path="audit.jsonl",
            created_at="2026-05-05T00:01:00+00:00",
        )

        self.assertEqual(payload["audit_dashboard_version"], "0.1")
        self.assertEqual(payload["cards"]["total_records"], 2)
        self.assertEqual(payload["aix"]["average"], 0.715)
        self.assertEqual(payload["aix"]["min"], 0.52)
        self.assertEqual(payload["hard_blockers"]["total"], 1)
        self.assertEqual(payload["shadow_mode"]["would_block_rate"], 1.0)
        self.assertTrue(any(item["id"] == "email_send_guardrail" for item in payload["adapter_breakdown"]))
        enterprise = next(item for item in payload["family_breakdown"] if item["id"] == "enterprise")
        personal = next(item for item in payload["family_breakdown"] if item["id"] == "personal_productivity")
        self.assertEqual(enterprise["adapter_usage"], 2)
        self.assertEqual(personal["shadow_would_block_rate"], 1.0)
        self.assertGreaterEqual(personal["human_review_escalations"], 1)
        self.assertGreaterEqual(personal["evidence_missing_rate"], 0.0)
        self.assertTrue(any(item["id"] == "support" for item in payload["role_breakdown"]))
        self.assertEqual(len(payload["violation_trends"]), 2)

    def test_aix_drift_report_flags_disallowed_decisions_and_low_scores(self):
        bad = sample_record(
            aix={
                "score": 0.4,
                "decision": "refuse",
                "components": {"P": 0.4},
                "beta": 1.5,
                "thresholds": {},
                "hard_blockers": ["unsafe_private_data"],
            }
        )

        report = agent_api.audit_aix_drift_report([bad], created_at="2026-05-05T00:02:00+00:00")

        self.assertFalse(report["valid"])
        paths = {issue["path"] for issue in report["issues"]}
        self.assertIn("$.metrics.aix_score_average", paths)
        self.assertIn("$.metrics.aix_score_min", paths)
        self.assertIn("$.metrics.aix_hard_blocker_count", paths)
        self.assertIn("$.metrics.aix_decision_count", paths)

    def test_reviewer_report_writes_markdown_summary(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = pathlib.Path(temp_dir)
            audit_log = temp_path / "audit.jsonl"
            metrics_path = temp_path / "metrics.json"
            drift_path = temp_path / "drift.json"
            manifest_path = temp_path / "manifest.json"
            report_path = temp_path / "reviewer-report.md"
            agent_api.append_audit_record(audit_log, sample_record())
            agent_api.export_audit_metrics_file(audit_log, output_path=metrics_path, created_at="2026-05-05T00:01:00+00:00")
            drift = agent_api.audit_aix_drift_report_file(audit_log, output_path=drift_path, created_at="2026-05-05T00:02:00+00:00")
            agent_api.create_audit_integrity_manifest(audit_log, manifest_path=manifest_path, created_at="2026-05-05T00:03:00+00:00")

            result = agent_api.write_audit_reviewer_report(
                audit_log,
                report_path,
                metrics_path=metrics_path,
                drift_report_path=drift_path,
                manifest_path=manifest_path,
                created_at="2026-05-05T00:04:00+00:00",
            )

            text = report_path.read_text(encoding="utf-8")
            self.assertTrue(drift["valid"], drift)
            self.assertEqual(result["audit_reviewer_report_version"], "0.1")
            self.assertIn("# AANA Audit Reviewer Report", text)
            self.assertIn("AIx drift valid: true", text)
            self.assertIn("unsupported_claim", text)
            self.assertNotIn("Customer card", text)

    def test_validate_metrics_export_rejects_missing_core_metrics(self):
        payload = {
            "audit_metrics_export_version": "0.1",
            "record_count": 1,
            "metrics": {},
            "summary": {},
            "unavailable_metrics": [],
        }

        report = agent_api.validate_audit_metrics_export(payload)

        self.assertFalse(report["valid"])
        self.assertTrue(any(issue["path"] == "$.metrics.audit_records_total" for issue in report["issues"]))


if __name__ == "__main__":
    unittest.main()
