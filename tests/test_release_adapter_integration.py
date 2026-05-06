import json
import unittest
from pathlib import Path

import aana
from scripts import run_adapter


ROOT = Path(__file__).resolve().parents[1]
DEPLOYMENT_WORKFLOW = ROOT / "examples" / "workflow_deployment_readiness.json"
DEPLOYMENT_ADAPTER = ROOT / "examples" / "deployment_readiness_adapter.json"

SAFE_DEPLOYMENT_CANDIDATE = (
    "Approve deployment: production config uses pinned image app:2026.05.06, "
    "debug=false, CI passed, release gates enabled, no credentials are exposed, "
    "rollback and roll-forward plan are verified, health checks and canary passed, "
    "migration compatibility and backfill are verified, dashboards alerts logs "
    "metrics traces owner and incident routing are ready."
)


class ReleaseAdapterIntegrationTests(unittest.TestCase):
    def deployment_workflow(self, candidate=None):
        workflow = json.loads(DEPLOYMENT_WORKFLOW.read_text(encoding="utf-8"))
        if candidate is not None:
            workflow["candidate"] = candidate
        return workflow

    def test_deployment_workflow_blocks_direct_execution_when_mi_readiness_blocks(self):
        result = aana.check_request(self.deployment_workflow())

        self.assertFalse(result["direct_execution_allowed"])
        self.assertEqual(result["production_mi_readiness"]["release_status"], "blocked")
        self.assertIn("no-hard-blockers", result["direct_execution_blockers"])
        self.assertIn("global-aix-threshold", result["direct_execution_blockers"])
        self.assertEqual(result["production_mi_readiness"]["recommended_action"], "refuse")

    def test_deployment_workflow_allows_direct_execution_only_after_mi_readiness_passes(self):
        result = aana.check_request(self.deployment_workflow(SAFE_DEPLOYMENT_CANDIDATE))

        self.assertTrue(result["direct_execution_allowed"])
        self.assertEqual(result["production_mi_readiness"]["release_status"], "ready")
        self.assertEqual(result["production_mi_readiness"]["recommended_action"], "accept")
        self.assertEqual(result["direct_execution_blockers"], [])
        self.assertEqual(result["production_mi_batch"]["global_aix"]["risk_tier"], "high")

    def test_direct_adapter_run_remains_blocked_without_evidence_even_for_clean_candidate(self):
        adapter = run_adapter.load_adapter(DEPLOYMENT_ADAPTER)
        result = run_adapter.run_adapter(
            adapter,
            "Review deployment readiness before production release.",
            SAFE_DEPLOYMENT_CANDIDATE,
        )

        self.assertFalse(result["direct_execution_allowed"])
        self.assertEqual(result["production_mi_readiness"]["release_status"], "blocked")
        self.assertIn("evidence-present", result["direct_execution_blockers"])

    def test_non_release_adapter_does_not_attach_release_execution_gate(self):
        result = aana.check(
            adapter="research_summary",
            request="Write a concise research brief. Use only Source A and Source B.",
            candidate="AANA makes constraints explicit [Source A].",
            evidence=["Source A: AANA makes constraints explicit."],
        )

        self.assertNotIn("production_mi_readiness", result)
        self.assertNotIn("direct_execution_allowed", result)


if __name__ == "__main__":
    unittest.main()
