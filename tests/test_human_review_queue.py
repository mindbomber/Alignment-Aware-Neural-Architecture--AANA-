import tempfile
import unittest
from pathlib import Path

from eval_pipeline.human_review_queue import (
    HUMAN_REVIEW_PACKET_TYPE,
    HUMAN_REVIEW_QUEUE_VERSION,
    enqueue_defer_reviews,
    human_review_packet,
    human_review_packets,
    load_human_review_queue_jsonl,
    validate_human_review_packet,
    validate_human_review_packets,
)


def deferred_result():
    return {
        "handoff_id": "release-agent-to-human-review",
        "workflow_id": "release-001",
        "sender": {"id": "release_agent", "type": "agent", "trust_tier": "system"},
        "recipient": {"id": "deployment_gate", "type": "adapter", "trust_tier": "system"},
        "gate_decision": "block",
        "recommended_action": "defer",
        "blockers": ["global-aix-threshold"],
        "violations": [{"code": "insufficient_correction_capacity"}],
        "aix": {
            "score": 0.82,
            "decision": "defer",
            "components": {"P": 0.9, "B": 0.85, "C": 0.75, "F": 0.8},
            "hard_blockers": ["global-aix-threshold"],
        },
        "handoff_aix": {
            "score": 0.82,
            "decision": "defer",
            "components": {"P": 0.9, "B": 0.85, "C": 0.75, "F": 0.8},
            "hard_blockers": ["global-aix-threshold"],
        },
        "propagated_risk": {
            "risk_count": 1,
            "propagation_count": 1,
            "has_propagated_risk": True,
            "risk_counts": {"hidden_assumption": 1},
            "severity_score": 3,
        },
        "audit_summary": {
            "handoff_id": "release-agent-to-human-review",
            "message_fingerprint": "abc123",
            "evidence_fingerprints": ["def456"],
        },
        "message": {"summary": "raw message must not be copied"},
        "evidence": [{"text": "raw evidence must not be copied"}],
    }


class HumanReviewQueueTests(unittest.TestCase):
    def test_human_review_packet_keeps_redacted_decision_metadata(self):
        packet = human_review_packet(deferred_result(), requested_human_decision="request_revision")

        self.assertEqual(packet["human_review_queue_version"], HUMAN_REVIEW_QUEUE_VERSION)
        self.assertEqual(packet["packet_type"], HUMAN_REVIEW_PACKET_TYPE)
        self.assertEqual(packet["requested_human_decision"], "request_revision")
        self.assertEqual(packet["blockers"], ["global-aix-threshold"])
        self.assertEqual(packet["aix"]["score"], 0.82)
        self.assertTrue(packet["propagated_risk"]["has_propagated_risk"])
        self.assertEqual(packet["fingerprints"]["message"], "abc123")
        self.assertNotIn("message", packet)
        self.assertNotIn("evidence", packet)
        self.assertTrue(validate_human_review_packet(packet)["valid"])

    def test_human_review_packets_filters_to_defer_routes(self):
        accepted = deferred_result()
        accepted["handoff_id"] = "accepted"
        accepted["recommended_action"] = "accept"
        workflow = {"results": [deferred_result(), accepted], "propagated_risk": deferred_result()["propagated_risk"]}

        packets = human_review_packets(workflow)

        self.assertEqual(len(packets), 1)
        self.assertEqual(packets[0]["handoff_id"], "release-agent-to-human-review")

    def test_enqueue_defer_reviews_writes_jsonl(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "review_queue.jsonl"
            result = enqueue_defer_reviews([deferred_result()], path, requested_human_decision="defer")
            loaded = load_human_review_queue_jsonl(path)

        self.assertEqual(result["packet_count"], 1)
        self.assertEqual(len(loaded), 1)
        self.assertTrue(validate_human_review_packets(loaded)["valid"])

    def test_validate_human_review_packet_rejects_raw_content_fields(self):
        packet = human_review_packet(deferred_result())
        packet["payload"] = "raw private payload"

        report = validate_human_review_packet(packet)

        self.assertFalse(report["valid"])
        self.assertTrue(any("Raw MI content" in issue["message"] for issue in report["issues"]))


if __name__ == "__main__":
    unittest.main()
