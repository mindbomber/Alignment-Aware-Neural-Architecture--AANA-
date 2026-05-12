import pathlib
import unittest

from eval_pipeline import pilot_certification
from scripts import aana_cli


ROOT = pathlib.Path(__file__).resolve().parents[1]


class DockerHttpBridgePackagingTests(unittest.TestCase):
    def test_docker_bridge_packaging_files_are_present(self):
        for relative_path in [
            "Dockerfile",
            "docker-compose.yml",
            ".dockerignore",
            "examples/aana_bridge.env.example",
            "docs/docker-http-bridge.md",
            "docs/production-candidate-deployment.md",
        ]:
            self.assertTrue((ROOT / relative_path).exists(), relative_path)

    def test_dockerfile_runs_fastapi_runtime(self):
        dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")

        self.assertIn("FROM python:3.11-slim", dockerfile)
        self.assertIn("EXPOSE 8765", dockerfile)
        self.assertIn('python -m pip install --no-cache-dir ".[api]"', dockerfile)
        self.assertIn("aana-fastapi", dockerfile)
        self.assertIn("AANA_MAX_REQUEST_BYTES", dockerfile)
        self.assertIn("data.get('status') == 'ok'", dockerfile)
        self.assertIn("COPY Dockerfile docker-compose.yml .dockerignore ./", dockerfile)
        self.assertIn("COPY .github ./.github", dockerfile)
        self.assertIn("COPY web ./web", dockerfile)
        self.assertIn("--host", dockerfile)
        self.assertIn("0.0.0.0", dockerfile)
        self.assertIn("--audit-log", dockerfile)
        self.assertIn("USER 10001", dockerfile)
        self.assertIn("HEALTHCHECK", dockerfile)

    def test_production_kubernetes_template_declares_hardened_runtime(self):
        manifest = (ROOT / "deploy" / "kubernetes" / "aana-bridge-production-template.yaml").read_text(encoding="utf-8")

        for expected in [
            "kind: Deployment",
            "kind: Service",
            "kind: Ingress",
            "nginx.ingress.kubernetes.io/force-ssl-redirect: \"true\"",
            "nginx.ingress.kubernetes.io/limit-rpm: \"60\"",
            "path: /health",
            "path: /ready",
            "aana-fastapi",
            "AANA_MAX_REQUEST_BYTES",
            "AANA_BRIDGE_TOKEN_SCOPES",
            "production_candidate_check",
            "resources:",
            "requests:",
            "limits:",
            "runAsNonRoot: true",
            "allowPrivilegeEscalation: false",
            "kubectl rollout undo deployment/aana-bridge -n aana-runtime",
        ]:
            self.assertIn(expected, manifest)

    def test_compose_wires_runtime_profiles_and_post_auth(self):
        compose = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")

        for expected in [
            "aana/enterprise-ops-runtime:local",
            "aana-fastapi",
            "AANA_BRIDGE_TOKEN",
            "aana-local-dev-token",
            "AANA_BRIDGE_TOKEN_SCOPES",
            "production_candidate_check",
            "AANA_ADAPTER_GALLERY",
            "examples/adapter_gallery.json",
            "AANA_AUDIT_LOG",
            "eval_outputs/audit/docker/aana-fastapi.jsonl",
            "AANA_MAX_REQUEST_BYTES",
            "data.get('status') == 'ok'",
            "./eval_outputs:/app/eval_outputs",
            "/ready",
        ]:
            self.assertIn(expected, compose)

    def test_env_example_declares_profile_bundle(self):
        env_example = (ROOT / "examples" / "aana_bridge.env.example").read_text(encoding="utf-8")

        for expected in [
            "AANA_DEPLOYMENT_MANIFEST=examples/production_deployment_internal_pilot.json",
            "AANA_GOVERNANCE_POLICY=examples/human_governance_policy_internal_pilot.json",
            "AANA_EVIDENCE_REGISTRY=examples/evidence_registry.json",
            "AANA_OBSERVABILITY_POLICY=examples/observability_policy_internal_pilot.json",
            "AANA_PRODUCTION_CANDIDATE_PROFILE=examples/production_candidate_profile_enterprise_support.json",
            "AANA_LIVE_CONNECTOR_CONFIG=examples/enterprise_support_live_connectors.json",
            "AANA_MAX_REQUEST_BYTES=1048576",
        ]:
            self.assertIn(expected, env_example)

    def test_docker_docs_cover_required_runtime_routes(self):
        docs = (ROOT / "docs" / "docker-http-bridge.md").read_text(encoding="utf-8")

        for expected in [
            "docker compose up --build",
            "Invoke-RestMethod http://localhost:8765/ready",
            "http://localhost:8765/docs",
            "aana-fastapi",
            "/production-candidate-check",
            "/enterprise-live-connectors",
            "/live-monitoring",
            "AANA_BRIDGE_TOKEN_SCOPES",
            "production_candidate_check",
            "not production certification",
            "examples/agent_event_support_reply.json",
            "examples/workflow_research_summary_structured.json",
            "examples/workflow_batch_productive_work.json",
        ]:
            self.assertIn(expected, docs)

    def test_production_candidate_deployment_doc_declares_artifacts_and_external_gates(self):
        docs = (ROOT / "docs" / "production-candidate-deployment.md").read_text(encoding="utf-8")

        for expected in [
            "docker build -t aana/enterprise-ops-runtime:local .",
            "docker compose up --build",
            "kubectl apply -f deploy/kubernetes/aana-bridge-production-template.yaml",
            "production-candidate-check",
            "eval_outputs/audit/docker/aana-fastapi.jsonl",
            "production-candidate AIx report",
            "Production-candidate does not mean production certification.",
            "live connector authorization",
            "immutable audit retention",
            "measured shadow-mode results",
        ]:
            self.assertIn(expected, docs)

    def test_pilot_certification_includes_docker_bridge_gate(self):
        report = pilot_certification.pilot_readiness_report(cli_commands=aana_cli.cli_command_matrix())
        bridge = next(surface for surface in report["surfaces"] if surface["surface_id"] == "http_bridge")
        gate_ids = {gate["id"] for gate in bridge["gates"]}

        self.assertIn("bridge_docker_package", gate_ids)
        self.assertIn("bridge_local_action_demos", gate_ids)
        self.assertTrue(bridge["ready"], bridge)


if __name__ == "__main__":
    unittest.main()
