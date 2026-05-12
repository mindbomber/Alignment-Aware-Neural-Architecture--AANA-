import json
import pathlib
import unittest

from eval_pipeline import production


ROOT = pathlib.Path(__file__).resolve().parents[1]


REQUIRED_ENV_KEYS = {
    "AANA_BRIDGE_TOKEN",
    "AANA_BRIDGE_PORT",
    "AANA_ADAPTER_GALLERY",
    "AANA_AUDIT_LOG",
    "AANA_MAX_REQUEST_BYTES",
    "AANA_RATE_LIMIT_PER_MINUTE",
    "AANA_EVIDENCE_REGISTRY",
    "AANA_PRODUCTION_CANDIDATE_PROFILE",
    "AANA_LIVE_CONNECTOR_CONFIG",
    "AANA_LIVE_MONITORING_CONFIG",
}


class DeploymentPackageTests(unittest.TestCase):
    def read_text(self, relative_path):
        return (ROOT / relative_path).read_text(encoding="utf-8")

    def load_json(self, relative_path):
        return json.loads(self.read_text(relative_path))

    def test_dockerfile_runs_fastapi_with_deployment_config(self):
        dockerfile = self.read_text("Dockerfile")

        self.assertIn("FROM python:3.11-slim", dockerfile)
        self.assertIn("aana-fastapi", dockerfile)
        self.assertIn('python -m pip install --no-cache-dir ".[api]"', dockerfile)
        self.assertIn("--host", dockerfile)
        self.assertIn("--gallery", dockerfile)
        self.assertIn("--audit-log", dockerfile)
        self.assertIn("--max-request-bytes", dockerfile)
        self.assertIn("--rate-limit-per-minute", dockerfile)
        self.assertIn("/ready", dockerfile)
        self.assertIn("data.get('status') == 'ok'", dockerfile)
        self.assertIn("HEALTHCHECK", dockerfile)
        for key in REQUIRED_ENV_KEYS - {"AANA_BRIDGE_TOKEN"}:
            self.assertIn(key, dockerfile)

    def test_compose_exposes_auth_audit_limits_and_readiness(self):
        compose = self.read_text("docker-compose.yml")

        for key in REQUIRED_ENV_KEYS:
            self.assertIn(key, compose)
        self.assertIn("aana/enterprise-ops-runtime:local", compose)
        self.assertIn("aana-fastapi", compose)
        self.assertIn("AANA_BRIDGE_TOKEN_SCOPES", compose)
        self.assertIn("production_candidate_check", compose)
        self.assertIn("/ready", compose)
        self.assertIn("data.get('status') == 'ok'", compose)
        self.assertIn("./eval_outputs:/app/eval_outputs", compose)

    def test_deploy_env_example_declares_required_runtime_knobs(self):
        env_example = self.read_text("examples/aana_bridge.env.example")

        for key in REQUIRED_ENV_KEYS:
            self.assertIn(f"{key}=", env_example)
        self.assertIn("AANA_DEPLOYMENT_MANIFEST=examples/production_deployment_internal_pilot.json", env_example)
        self.assertIn("AANA_GOVERNANCE_POLICY=examples/human_governance_policy_internal_pilot.json", env_example)
        self.assertIn("AANA_OBSERVABILITY_POLICY=examples/observability_policy_internal_pilot.json", env_example)

    def test_kubernetes_manifest_declares_runtime_health_and_audit_boundaries(self):
        manifest = self.read_text("deploy/kubernetes/aana-bridge.yaml")

        for required in (
            "kind: Secret",
            "kind: ConfigMap",
            "kind: PersistentVolumeClaim",
            "kind: Deployment",
            "kind: Service",
            "AANA_BRIDGE_TOKEN",
            "AANA_AUDIT_LOG",
            "AANA_EVIDENCE_REGISTRY",
            "AANA_MAX_REQUEST_BYTES",
            "AANA_BRIDGE_TOKEN_SCOPES",
            "aana-fastapi",
            "livenessProbe:",
            "readinessProbe:",
            "path: /health",
            "path: /ready",
        ):
            self.assertIn(required, manifest)

    def test_local_and_production_kubernetes_profiles_are_explicit(self):
        internal = self.read_text("deploy/kubernetes/aana-bridge-internal-pilot.yaml")
        production_template = self.read_text("deploy/kubernetes/aana-bridge-production-template.yaml")

        self.assertIn("internal-pilot", internal)
        self.assertIn("pilot-ready-not-production-certified", internal)
        self.assertIn("examples/production_deployment_internal_pilot.json", internal)
        self.assertIn("examples/evidence_registry.json", internal)

        self.assertIn("production-template", production_template)
        self.assertIn("requires-external-evidence-and-owner-signoff", production_template)
        self.assertIn("kind: Deployment", production_template)
        self.assertIn("kind: Ingress", production_template)
        self.assertIn("path: /health", production_template)
        self.assertIn("path: /ready", production_template)
        self.assertIn("kubectl rollout undo deployment/aana-bridge -n aana-runtime", production_template)
        self.assertIn("replace-with-approved-evidence-registry", production_template)

    def test_repo_deployment_manifests_remain_validator_clean(self):
        internal = self.load_json("examples/production_deployment_internal_pilot.json")
        template = self.load_json("examples/production_deployment_template.json")

        internal_report = production.validate_deployment_manifest(internal)
        template_report = production.validate_deployment_manifest(template)

        self.assertTrue(internal_report["production_ready"], internal_report)
        self.assertTrue(template_report["valid"], template_report)
        self.assertEqual(template_report["errors"], 0, template_report)

    def test_internal_pilot_manifest_names_support_evidence_connectors(self):
        manifest = self.load_json("examples/production_deployment_internal_pilot.json")
        source_ids = {source["source_id"] for source in manifest["evidence_sources"]}

        self.assertIn("crm-record", source_ids)
        self.assertIn("support-policy", source_ids)
        self.assertIn("order-system", source_ids)
        self.assertTrue(manifest["bridge"]["auth_required"])
        self.assertTrue(manifest["audit"]["redaction_required"])


if __name__ == "__main__":
    unittest.main()
