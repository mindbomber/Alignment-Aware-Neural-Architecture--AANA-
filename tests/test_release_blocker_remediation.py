import json
import tempfile
import unittest
from pathlib import Path

from eval_pipeline.release_blocker_remediation import (
    corrected_research_citation_handoffs,
    run_research_citation_remediation,
    write_research_citation_remediation,
)


class ReleaseBlockerRemediationTests(unittest.TestCase):
    def test_corrected_handoffs_remove_unsupported_productivity_and_source_c_claims(self):
        handoffs = corrected_research_citation_handoffs()
        encoded = json.dumps(handoffs, sort_keys=True)

        self.assertNotIn("40%", encoded)
        self.assertNotIn("Source C supports", encoded)
        self.assertNotIn("source-c", encoded)

    def test_remediation_resolves_release_readiness_blockers(self):
        result = run_research_citation_remediation()
        after = result["after"]["production_mi_readiness"]

        self.assertEqual(result["status"], "pass")
        self.assertIn("no-hard-blockers", result["resolved_blockers"])
        self.assertIn("global-aix-threshold", result["resolved_blockers"])
        self.assertIn("propagation-resolved", result["resolved_blockers"])
        self.assertEqual(result["remaining_blockers"], [])
        self.assertEqual(after["release_status"], "ready")
        self.assertEqual(after["global_aix"]["score"], 1.0)
        self.assertEqual(after["propagated_risk"]["risk_count"], 0)

    def test_remediation_executes_correction_loop_before_final_recheck(self):
        result = run_research_citation_remediation()
        loop = result["correction_loop"]

        self.assertTrue(loop["executed"])
        self.assertEqual(loop["route"], "revise_upstream_output")
        self.assertLess(
            result["before"]["production_mi_readiness"]["global_aix"]["score"],
            result["after"]["production_mi_readiness"]["global_aix"]["score"],
        )

    def test_write_remediation_outputs_updated_pilot_artifacts(self):
        with tempfile.TemporaryDirectory() as directory:
            payload = write_research_citation_remediation(directory)
            paths = {key: Path(value) for key, value in payload["paths"].items()}
            pilot = json.loads(paths["pilot_result"].read_text(encoding="utf-8"))
            readiness = json.loads(paths["production_mi_readiness"].read_text(encoding="utf-8"))
            release_report = json.loads(paths["release_readiness_report"].read_text(encoding="utf-8"))
            self.assertTrue(paths["release_blocker_remediation"].exists())
            self.assertTrue(paths["mi_audit_jsonl"].exists())

        self.assertEqual(pilot["accepted"], True)
        self.assertEqual(readiness["release_status"], "ready")
        self.assertEqual(release_report["status"], "pass")


if __name__ == "__main__":
    unittest.main()
