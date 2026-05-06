import json
import pathlib
import unittest

from eval_pipeline import production

ROOT = pathlib.Path(__file__).resolve().parents[1]


class ProductionManifestTests(unittest.TestCase):
    def valid_manifest(self):
        return {
            "deployment_name": "aana-prod",
            "environment": "production",
            "bridge": {
                "host": "127.0.0.1",
                "auth_required": True,
                "tls_terminated": True,
                "tls": {
                    "termination": "managed ingress",
                    "ingress_class": "nginx-internal",
                    "certificate_ref": "aana-runtime/aana-bridge-tls",
                    "minimum_tls_version": "TLSv1.2",
                    "https_only": True,
                },
                "max_body_bytes": 1048576,
                "rate_limits": {
                    "enabled": True,
                    "requests_per_minute": 60,
                    "burst": 15,
                    "runtime_enforced": True,
                    "edge_enforced": True,
                },
            },
            "container": {
                "image": "registry.example/aana/http-bridge:0.1",
                "image_pull_policy": "IfNotPresent",
                "command": "python scripts/aana_server.py",
                "probes": {
                    "liveness": {"path": "/health", "period_seconds": 10},
                    "readiness": {"path": "/ready", "period_seconds": 10},
                },
                "resources": {
                    "requests": {"cpu": "250m", "memory": "512Mi"},
                    "limits": {"cpu": "1", "memory": "1Gi"},
                },
            },
            "kubernetes": {
                "manifest": "deploy/kubernetes/aana-bridge-production-template.yaml",
                "namespace": "aana-runtime",
                "service_name": "aana-bridge",
                "ingress_name": "aana-bridge",
                "health_endpoint": "/health",
                "readiness_endpoint": "/ready",
                "rollback_command": "kubectl rollout undo deployment/aana-bridge -n aana-runtime",
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
                "tracked_metrics": [
                    "aix_decision_count",
                    "aix_hard_blocker_count",
                    "aix_score_average",
                    "connector_failure_count",
                    "evidence_freshness_failure_count",
                    "gate_decision_count",
                    "recommended_action_count",
                    "refusal_defer_rate",
                    "violation_code_count",
                    "latency",
                ],
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
            "incident_response": {
                "owner": "AANA Production On-Call",
                "incident_channel": "AANA Incident Channel",
                "rollback_path": "kubectl rollout undo deployment/aana-bridge -n aana-runtime",
                "rollback_trigger": "critical false accept",
                "last_known_good_artifact": "registry.example/aana/http-bridge:0.1-last-known-good",
                "rollback_steps": ["page on-call", "roll back deployment", "verify readiness"],
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

    def test_manifest_requires_deployment_hardening_fields(self):
        manifest = self.valid_manifest()
        manifest["bridge"]["tls"]["https_only"] = False
        manifest["bridge"]["rate_limits"]["edge_enforced"] = False
        manifest["container"]["probes"]["readiness"]["path"] = "/health"
        manifest["container"]["resources"]["limits"].pop("memory")
        manifest["kubernetes"]["rollback_command"] = "replace with rollback"
        manifest["incident_response"]["rollback_steps"] = []

        report = production.validate_deployment_manifest(manifest)

        self.assertFalse(report["valid"])
        paths = {issue["path"] for issue in report["issues"]}
        self.assertIn("$.bridge.tls.https_only", paths)
        self.assertIn("$.bridge.rate_limits.edge_enforced", paths)
        self.assertIn("$.container.probes.readiness.path", paths)
        self.assertIn("$.container.resources.limits.memory", paths)
        self.assertIn("$.kubernetes.rollback_command", paths)
        self.assertIn("$.incident_response.rollback_steps", paths)

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
            "dashboards": [
                {
                    "id": "aana-runtime",
                    "title": "AANA Runtime Dashboard",
                    "url": "https://observability.local/aana",
                    "metrics_source": "eval_outputs/audit/ci/aana-ci-metrics.json",
                    "owner": "AANA Maintainers",
                    "panels": [
                        {"id": "gate_decisions", "title": "Gate Decisions", "metric": "gate_decision_count"},
                        {"id": "recommended_actions", "title": "Recommended Actions", "metric": "recommended_action_count"},
                        {"id": "refusal_defer_rate", "title": "Refusal Defer Rate", "metric": "refusal_defer_rate"},
                        {"id": "connector_failures", "title": "Connector Failures", "metric": "connector_failure_count"},
                        {"id": "evidence_freshness", "title": "Evidence Freshness", "metric": "evidence_freshness_failure_count"},
                        {"id": "latency", "title": "Latency", "metric": "latency.p95_ms"},
                        {"id": "aix_drift", "title": "AIx Drift", "metric": "aix_score_average"},
                        {"id": "hard_blockers", "title": "Hard Blockers", "metric": "aix_hard_blocker_count"},
                    ],
                }
            ],
            "tracked_metrics": [
                "connector_failure_count",
                "evidence_freshness_failure_count",
                "gate_decision_count",
                "recommended_action_count",
                "violation_code_count",
                "aix_score_average",
                "aix_decision_count",
                "aix_hard_blocker_count",
                "refusal_defer_rate",
                "latency",
            ],
            "alerts": [
                {
                    "id": "high_refusal_defer_rate",
                    "name": "High refusal/defer rate",
                    "metric": "refusal_defer_rate",
                    "condition": "greater_than",
                    "threshold": 0.2,
                    "severity": "high",
                    "route": "AANA Local Incident Log",
                    "owner": "AANA Local On-Call",
                },
                {
                    "id": "connector_failures",
                    "name": "Connector failures",
                    "metric": "connector_failure_count",
                    "condition": "greater_than",
                    "threshold": 0,
                    "severity": "critical",
                    "route": "AANA Local Incident Log",
                    "owner": "AANA Local On-Call",
                },
                {
                    "id": "stale_evidence",
                    "name": "Stale evidence",
                    "metric": "evidence_freshness_failure_count",
                    "condition": "greater_than",
                    "threshold": 0,
                    "severity": "high",
                    "route": "AANA Local Incident Log",
                    "owner": "AANA Local On-Call",
                },
                {
                    "id": "latency_spike",
                    "name": "P95 latency breach",
                    "metric": "latency.p95_ms",
                    "condition": "greater_than",
                    "threshold": 2000,
                    "severity": "medium",
                    "route": "AANA Local Incident Log",
                    "owner": "AANA Local On-Call",
                },
                {
                    "id": "aix_drift",
                    "name": "AIx drift",
                    "metric": "aix_score_average",
                    "condition": "less_than",
                    "threshold": 0.85,
                    "severity": "high",
                    "route": "AANA Local Incident Log",
                    "owner": "AANA Local On-Call",
                },
                {
                    "id": "hard_blocker_spike",
                    "name": "Hard blocker spike",
                    "metric": "aix_hard_blocker_count",
                    "condition": "greater_than",
                    "threshold": 0,
                    "severity": "high",
                    "route": "AANA Local Incident Log",
                    "owner": "AANA Local On-Call",
                }
            ],
            "drift_review": {
                "cadence": "weekly",
                "owner": "AANA Maintainers",
                "required_reports": ["top_violation_codes", "aix_score_trend", "connector_failure_trend"],
            },
            "latency_slo": {
                "p95_ms": 2000,
                "route": "AANA Local Incident Log",
            },
            "on_call": {
                "primary": "AANA Local On-Call",
                "secondary": "AANA Maintainers",
                "schedule": "https://observability.local/aana/on-call",
                "escalation_policy": "AANA Local Severity Policy",
                "handoff": "Local handoff",
                "incident_channel": "AANA Local Incident Log",
                "page_for": ["high_refusal_defer_rate"],
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
        self.assertTrue(any("aix_score_average" in issue["message"] for issue in report["issues"]))

    def test_observability_policy_requires_dashboard_alert_coverage_and_on_call(self):
        policy = self.valid_observability_policy()
        policy["alerts"] = [alert for alert in policy["alerts"] if alert["id"] != "connector_failures"]
        policy["dashboards"][0]["panels"] = [panel for panel in policy["dashboards"][0]["panels"] if panel["id"] != "connector_failures"]
        policy["on_call"].pop("primary")

        report = production.validate_observability_policy(policy)

        self.assertFalse(report["valid"])
        messages = " ".join(issue["message"] for issue in report["issues"])
        paths = {issue["path"] for issue in report["issues"]}
        self.assertIn("connector_failures", messages)
        self.assertIn("$.on_call.primary", paths)

    def test_deployment_manifest_requires_aix_observability_metrics(self):
        manifest = self.valid_manifest()
        manifest["observability"]["tracked_metrics"] = ["gate_decision_count", "latency"]

        report = production.validate_deployment_manifest(manifest)

        self.assertFalse(report["valid"])
        self.assertTrue(any(issue["path"] == "$.observability.tracked_metrics" for issue in report["issues"]))
        self.assertTrue(any("aix_score_average" in issue["message"] for issue in report["issues"]))

    def test_observability_policy_rejects_missing_alert_threshold(self):
        policy = self.valid_observability_policy()
        policy["alerts"][0].pop("threshold")

        report = production.validate_observability_policy(policy)

        self.assertFalse(report["valid"])
        self.assertTrue(any(issue["path"] == "$.alerts[0].threshold" for issue in report["issues"]))

    def test_aix_audit_metrics_accepts_clean_release_metrics(self):
        metrics = {
            "record_count": 2,
            "metrics": {
                "aix_score_average": 0.95,
                "aix_score_min": 0.9,
                "aix_hard_blocker_count": 0,
                "aix_decision_count": 2,
                "aix_decision_count.accept": 1,
                "aix_decision_count.revise": 1,
            },
        }

        report = production.validate_aix_audit_metrics(metrics)

        self.assertTrue(report["valid"], report)
        self.assertTrue(report["production_ready"], report)

    def test_aix_audit_metrics_rejects_low_score_hard_blockers_and_decision_drift(self):
        metrics = {
            "record_count": 2,
            "metrics": {
                "aix_score_average": 0.7,
                "aix_score_min": 0.4,
                "aix_hard_blocker_count": 1,
                "aix_decision_count": 2,
                "aix_decision_count.accept": 1,
                "aix_decision_count.refuse": 1,
            },
        }

        report = production.validate_aix_audit_metrics(metrics)

        self.assertFalse(report["valid"])
        messages = " ".join(issue["message"] for issue in report["issues"])
        self.assertIn("average score", messages)
        self.assertIn("hard-blocker count", messages)
        self.assertIn("decision drift", messages)

    def test_internal_pilot_profiles_are_production_ready(self):
        deployment = json.loads((ROOT / "examples" / "production_deployment_internal_pilot.json").read_text())
        governance = json.loads((ROOT / "examples" / "human_governance_policy_internal_pilot.json").read_text())
        observability = json.loads((ROOT / "examples" / "observability_policy_internal_pilot.json").read_text())

        deployment_report = production.validate_deployment_manifest(deployment)
        governance_report = production.validate_governance_policy(governance)
        observability_report = production.validate_observability_policy(observability)

        self.assertTrue(deployment_report["production_ready"], deployment_report)
        self.assertTrue(governance_report["production_ready"], governance_report)
        self.assertTrue(observability_report["production_ready"], observability_report)


if __name__ == "__main__":
    unittest.main()
