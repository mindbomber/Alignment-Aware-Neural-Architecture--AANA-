import unittest

from eval_pipeline import production


class ProductionManifestTests(unittest.TestCase):
    def valid_manifest(self):
        return {
            "deployment_name": "aana-prod",
            "environment": "production",
            "bridge": {
                "host": "127.0.0.1",
                "auth_required": True,
                "tls_terminated": True,
                "max_body_bytes": 1048576,
                "rate_limits": {"enabled": True, "requests_per_minute": 60},
            },
            "audit": {
                "sink": "s3://audit-bucket/aana/",
                "immutable": True,
                "retention_days": 365,
                "raw_artifact_store": "none",
                "redaction_required": True,
            },
            "evidence_sources": [
                {
                    "source_id": "source-a",
                    "owner": "Research Ops",
                    "authorization": "service-account:aana-readonly",
                    "freshness_slo": "24h",
                    "trust_tier": "verified",
                }
            ],
            "observability": {
                "dashboard_url": "https://observability.example/aana",
                "alerts_enabled": True,
                "tracked_metrics": ["gate_decision_count", "violation_code_count"],
            },
            "domain_owners": [
                {
                    "adapter_id": "research_summary",
                    "owner": "Research Ops",
                    "review_status": "approved",
                }
            ],
            "human_review": {
                "queue": "Research Ops Review",
                "required_for": ["high-impact decisions"],
                "sla": "1 business day",
            },
        }

    def test_valid_manifest_is_production_ready(self):
        report = production.validate_deployment_manifest(self.valid_manifest())

        self.assertTrue(report["valid"], report)
        self.assertTrue(report["production_ready"], report)
        self.assertEqual(report["errors"], 0)
        self.assertEqual(report["warnings"], 0)

    def test_manifest_requires_auth_tls_and_rate_limits(self):
        manifest = self.valid_manifest()
        manifest["bridge"]["auth_required"] = False
        manifest["bridge"]["tls_terminated"] = False
        manifest["bridge"]["rate_limits"]["enabled"] = False

        report = production.validate_deployment_manifest(manifest)

        self.assertFalse(report["valid"])
        paths = {issue["path"] for issue in report["issues"]}
        self.assertIn("$.bridge.auth_required", paths)
        self.assertIn("$.bridge.tls_terminated", paths)
        self.assertIn("$.bridge.rate_limits.enabled", paths)

    def test_manifest_rejects_placeholder_operational_fields(self):
        manifest = self.valid_manifest()
        manifest["audit"]["sink"] = "replace with sink"
        manifest["evidence_sources"][0]["owner"] = "replace with owner"
        manifest["human_review"]["queue"] = "replace with queue"

        report = production.validate_deployment_manifest(manifest)

        self.assertFalse(report["valid"])
        paths = {issue["path"] for issue in report["issues"]}
        self.assertIn("$.audit.sink", paths)
        self.assertIn("$.evidence_sources[0].owner", paths)
        self.assertIn("$.human_review.queue", paths)

    def valid_governance_policy(self):
        return {
            "policy_name": "AANA Production Governance",
            "owner": "Safety Review",
            "review_cadence": "weekly",
            "escalation_classes": [
                {
                    "name": "high-impact decision",
                    "trigger": "medical, legal, financial, safety, private-data, or irreversible action",
                    "route": "Safety Review Queue",
                    "allowed_actions": ["ask", "defer", "refuse"],
                }
            ],
            "decision_explanations": {
                "ask": "I need more information before checking this safely.",
                "defer": "This needs stronger evidence or review before action.",
                "refuse": "I cannot help because the request violates a required boundary.",
            },
            "review_metrics": ["false_accept_rate", "false_block_rate"],
            "incident_response": {
                "owner": "Safety Review",
                "severity_levels": ["low", "medium", "high"],
                "rollback_trigger": "critical false accept",
                "notification_path": "incident-channel",
            },
        }

    def test_valid_governance_policy_is_production_ready(self):
        report = production.validate_governance_policy(self.valid_governance_policy())

        self.assertTrue(report["valid"], report)
        self.assertTrue(report["production_ready"], report)

    def test_governance_policy_rejects_placeholders(self):
        policy = self.valid_governance_policy()
        policy["owner"] = "replace with owner"
        policy["decision_explanations"]["defer"] = "replace with defer explanation"

        report = production.validate_governance_policy(policy)

        self.assertFalse(report["valid"])
        paths = {issue["path"] for issue in report["issues"]}
        self.assertIn("$.owner", paths)
        self.assertIn("$.decision_explanations.defer", paths)

    def valid_observability_policy(self):
        return {
            "policy_name": "AANA Observability",
            "owner": "AANA Maintainers",
            "dashboard_url": "https://observability.local/aana",
            "tracked_metrics": [
                "gate_decision_count",
                "recommended_action_count",
                "violation_code_count",
                "latency",
            ],
            "alerts": [
                {
                    "name": "high false accept rate",
                    "metric": "false_accept_rate",
                    "condition": "greater_than",
                    "threshold": 0.01,
                    "severity": "critical",
                    "route": "AANA Local Incident Log",
                }
            ],
            "drift_review": {
                "cadence": "weekly",
                "owner": "AANA Maintainers",
                "required_reports": ["top_violation_codes"],
            },
            "latency_slo": {
                "p95_ms": 2000,
                "route": "AANA Local Incident Log",
            },
        }

    def test_valid_observability_policy_is_production_ready(self):
        report = production.validate_observability_policy(self.valid_observability_policy())

        self.assertTrue(report["valid"], report)
        self.assertTrue(report["production_ready"], report)

    def test_observability_policy_requires_core_metrics(self):
        policy = self.valid_observability_policy()
        policy["tracked_metrics"] = ["latency"]

        report = production.validate_observability_policy(policy)

        self.assertFalse(report["valid"])
        self.assertTrue(any(issue["path"] == "$.tracked_metrics" for issue in report["issues"]))

    def test_observability_policy_rejects_missing_alert_threshold(self):
        policy = self.valid_observability_policy()
        policy["alerts"][0].pop("threshold")

        report = production.validate_observability_policy(policy)

        self.assertFalse(report["valid"])
        self.assertTrue(any(issue["path"] == "$.alerts[0].threshold" for issue in report["issues"]))


if __name__ == "__main__":
    unittest.main()
