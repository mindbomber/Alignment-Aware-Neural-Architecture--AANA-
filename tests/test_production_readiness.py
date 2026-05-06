import json
import tempfile
import unittest
from pathlib import Path

from eval_pipeline.mi_pilot import run_research_citation_mi_pilot
from eval_pipeline.production_readiness import (
    PRODUCTION_MI_READINESS_VERSION,
    production_mi_readiness_gate,
    production_mi_release_checklist_markdown,
    write_production_mi_readiness_result,
    write_production_mi_release_checklist,
)


def clean_batch():
    return {
        "results": [
            {
                "handoff_id": "release-agent-to-deploy-gate",
                "gate_decision": "pass",
                "recommended_action": "accept",
                "evidence_summary": [{"source_id": "ci", "trust_tier": "verified"}],
                "aix": {"score": 0.96, "decision": "accept", "hard_blockers": []},
                "handoff_aix": {"score": 0.96, "decision": "accept", "hard_blockers": []},
            }
        ],
        "global_aix": {
            "score": 0.96,
            "decision": "accept",
            "recommended_action": "accept",
            "risk_tier": "high",
            "thresholds": {"accept": 0.93, "revise": 0.75, "defer": 0.6},
            "hard_blockers": [],
        },
        "propagated_risk": {
            "risk_count": 0,
            "propagation_count": 0,
            "has_propagated_risk": False,
        },
    }


class ProductionReadinessTests(unittest.TestCase):
    def test_clean_high_risk_batch_can_execute(self):
        result = production_mi_readiness_gate(clean_batch())

        self.assertEqual(result["production_mi_readiness_version"], PRODUCTION_MI_READINESS_VERSION)
        self.assertTrue(result["can_execute_directly"])
        self.assertEqual(result["release_status"], "ready")
        self.assertEqual(result["recommended_action"], "accept")

    def test_blocks_when_evidence_is_missing(self):
        batch = clean_batch()
        batch["results"][0]["evidence_summary"] = []
        result = production_mi_readiness_gate(batch)

        self.assertFalse(result["can_execute_directly"])
        self.assertEqual(result["release_status"], "blocked")
        self.assertEqual(result["recommended_action"], "retrieve")
        self.assertIn("evidence-present", result["blockers"])
        self.assertEqual(result["missing_evidence_handoff_ids"], ["release-agent-to-deploy-gate"])

    def test_blocks_when_hard_blockers_exist(self):
        batch = clean_batch()
        batch["global_aix"]["hard_blockers"] = ["production_deploy_without_approval"]
        result = production_mi_readiness_gate(batch)

        self.assertFalse(result["can_execute_directly"])
        self.assertEqual(result["recommended_action"], "refuse")
        self.assertIn("no-hard-blockers", result["blockers"])

    def test_blocks_when_global_aix_is_below_threshold(self):
        batch = clean_batch()
        batch["global_aix"]["score"] = 0.82
        result = production_mi_readiness_gate(batch)

        self.assertFalse(result["can_execute_directly"])
        self.assertIn("global-aix-threshold", result["blockers"])

    def test_blocks_pilot_with_unresolved_propagated_assumptions(self):
        pilot = run_research_citation_mi_pilot()
        result = production_mi_readiness_gate(pilot)

        self.assertFalse(result["can_execute_directly"])
        self.assertIn("propagation-resolved", result["blockers"])
        self.assertGreater(result["propagated_risk"]["risk_count"], 0)

    def test_blocks_when_mi_checks_are_missing(self):
        result = production_mi_readiness_gate({"global_aix": clean_batch()["global_aix"]})

        self.assertFalse(result["can_execute_directly"])
        self.assertIn("mi-checks-present", result["blockers"])

    def test_write_checklist_and_result_artifacts(self):
        with tempfile.TemporaryDirectory() as directory:
            checklist_path = Path(directory) / "production-mi-release-checklist.md"
            result_path = Path(directory) / "readiness.json"
            checklist = write_production_mi_release_checklist(checklist_path)
            payload = write_production_mi_readiness_result(clean_batch(), result_path)

            written_result = json.loads(result_path.read_text(encoding="utf-8"))
            written_checklist = checklist_path.read_text(encoding="utf-8")

        self.assertGreater(checklist["bytes"], 0)
        self.assertIn("Production MI Release Checklist", production_mi_release_checklist_markdown())
        self.assertIn("Global AIx", written_checklist)
        self.assertEqual(payload["result"]["release_status"], "ready")
        self.assertEqual(written_result["release_status"], "ready")


if __name__ == "__main__":
    unittest.main()
