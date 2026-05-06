import json
import tempfile
import unittest
from pathlib import Path

from eval_pipeline.human_review_queue import load_human_review_queue_jsonl, validate_human_review_packets
from eval_pipeline.pilot_hardening import (
    guarded_pilot_execution_decision,
    run_guarded_research_citation_pilot,
    write_guarded_research_citation_pilot,
)


class PilotHardeningTests(unittest.TestCase):
    def test_guarded_live_research_pilot_blocks_direct_execution_when_readiness_blocks(self):
        result = run_guarded_research_citation_pilot(allow_direct_execution=True, live_mode=True)

        self.assertEqual(result["pilot_mode"], "guarded_live")
        self.assertEqual(result["production_mi_readiness"]["release_status"], "blocked")
        self.assertFalse(result["direct_execution"]["direct_execution_allowed"])
        self.assertEqual(result["direct_execution"]["execution_state"], "blocked_not_executed")
        self.assertTrue(result["rollback"]["rollback_required"])
        self.assertFalse(result["rollback"]["external_action_taken"])
        self.assertTrue(result["rollback"]["defer_to_human_review"])
        self.assertGreaterEqual(result["human_review_queue"]["packet_count"], 1)
        self.assertTrue(result["human_review_queue"]["validation"]["valid"])

    def test_guarded_live_requires_explicit_direct_execution_even_when_readiness_passes(self):
        readiness = {
            "can_execute_directly": True,
            "release_status": "ready",
            "recommended_action": "accept",
        }

        held = guarded_pilot_execution_decision(readiness, allow_direct_execution=False)
        allowed = guarded_pilot_execution_decision(readiness, allow_direct_execution=True)

        self.assertTrue(held["readiness_passed"])
        self.assertFalse(held["direct_execution_allowed"])
        self.assertEqual(held["execution_state"], "readiness_passed_direct_execution_not_requested")
        self.assertTrue(allowed["direct_execution_allowed"])
        self.assertEqual(allowed["execution_state"], "ready_for_direct_execution")

    def test_write_guarded_pilot_outputs_hardening_artifacts(self):
        with tempfile.TemporaryDirectory() as directory:
            payload = write_guarded_research_citation_pilot(directory, allow_direct_execution=True)
            paths = {key: Path(value) for key, value in payload["paths"].items()}
            guarded = json.loads(paths["guarded_live_result"].read_text(encoding="utf-8"))
            readiness = json.loads(paths["production_mi_readiness"].read_text(encoding="utf-8"))
            review_packets = load_human_review_queue_jsonl(paths["human_review_queue"])

        self.assertEqual(guarded["pilot_hardening_version"], "0.1")
        self.assertEqual(readiness["release_status"], "blocked")
        self.assertGreaterEqual(len(review_packets), 1)
        self.assertTrue(validate_human_review_packets(review_packets)["valid"])

    def test_guarded_pilot_review_packets_are_redacted(self):
        result = run_guarded_research_citation_pilot(allow_direct_execution=True)
        packets = result["human_review_queue"]["packets"]

        self.assertGreaterEqual(len(packets), 1)
        packet = packets[0]
        self.assertNotIn("message", packet)
        self.assertNotIn("candidate", packet)
        self.assertNotIn("evidence", packet)
        self.assertTrue(validate_human_review_packets(packets)["valid"])


if __name__ == "__main__":
    unittest.main()
