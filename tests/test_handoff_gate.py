import unittest

from eval_pipeline.handoff_gate import handoff_gate


def clean_handoff():
    return {
        "contract_version": "0.1",
        "handoff_id": "research-agent-to-publication-check-001",
        "sender": {"id": "research_agent", "type": "agent", "trust_tier": "system"},
        "recipient": {"id": "publication_checker", "type": "adapter", "adapter_id": "publication_check"},
        "message_schema": {
            "kind": "candidate_answer",
            "schema_id": "publication-summary-v0.1",
            "content_type": "text/plain",
            "redaction_required": True,
        },
        "message": {
            "summary": "Candidate summary only claims what Source A supports.",
            "payload_redaction_status": "redacted",
            "claims": ["Source A supports the narrow claim."],
            "assumptions": [
                {
                    "id": "source-a-is-current",
                    "description": "Source A is current for the summary.",
                    "support_status": "supported",
                    "evidence_source_id": "source-a",
                }
            ],
        },
        "evidence": [
            {
                "source_id": "source-a",
                "retrieved_at": "2026-05-05T00:00:00Z",
                "trust_tier": "verified",
                "redaction_status": "redacted",
                "text": "Source A supports the narrow claim.",
                "retrieval_url": "aana://evidence/source-a",
                "supports": ["Source A supports the narrow claim."],
            }
        ],
        "constraint_map": {
            "K_P": [
                {
                    "id": "claim-supported",
                    "description": "All claims must be supported by cited evidence.",
                    "severity": "high",
                    "hard": True,
                    "source": "publication_check",
                }
            ],
            "K_B": [
                {
                    "id": "no-misleading-certainty",
                    "description": "Do not present uncertain evidence as settled.",
                    "severity": "medium",
                    "hard": True,
                    "source": "publication_check",
                }
            ],
            "K_C": [
                {
                    "id": "use-approved-sources",
                    "description": "Use only approved sources.",
                    "severity": "high",
                    "hard": True,
                    "source": "publication_check",
                }
            ],
            "F": [
                {
                    "id": "fresh-evidence",
                    "description": "Evidence must include retrieval time.",
                    "severity": "medium",
                    "hard": False,
                    "source": "evidence_registry",
                }
            ],
        },
        "verifier_scores": {
            "P": {"score": 1.0, "status": "pass", "confidence": 0.95, "verifier_ids": ["claim_support"]},
            "B": {"score": 0.95, "status": "pass", "confidence": 0.9, "verifier_ids": ["certainty"]},
            "C": {"score": 1.0, "status": "pass", "confidence": 0.95, "verifier_ids": ["source_policy"]},
            "F": {"score": 1.0, "status": "pass", "confidence": 0.9, "verifier_ids": ["freshness"]},
            "overall": 0.98,
        },
        "allowed_actions": ["accept", "revise", "retrieve", "ask", "defer", "refuse"],
        "metadata": {"aix": {"thresholds": {"accept": 0.85, "revise": 0.65, "defer": 0.5}}},
    }


class HandoffGateTests(unittest.TestCase):
    def test_accepts_constraint_coherent_handoff(self):
        result = handoff_gate(clean_handoff())

        self.assertEqual(result["gate_decision"], "pass")
        self.assertEqual(result["recommended_action"], "accept")
        self.assertEqual(result["aix"]["decision"], "accept")
        self.assertFalse(result["violations"])
        self.assertEqual(result["feasible_region"]["K_P"], ["claim-supported"])
        self.assertEqual(result["feasible_region"]["K_B"], ["no-misleading-certainty"])
        self.assertEqual(result["feasible_region"]["K_C"], ["use-approved-sources"])

    def test_blocks_when_recipient_task_constraint_fails(self):
        handoff = clean_handoff()
        handoff["verifier_scores"]["C"] = {
            "score": 0.1,
            "status": "fail",
            "confidence": 0.95,
            "verifier_ids": ["source_policy"],
        }

        result = handoff_gate(handoff)

        self.assertEqual(result["gate_decision"], "block")
        self.assertEqual(result["recommended_action"], "revise")
        self.assertIn("use-approved-sources", result["aix"]["hard_blockers"])
        self.assertTrue(any(violation["code"] == "C_verifier_failed" for violation in result["violations"]))

    def test_routes_missing_evidence_to_retrieve(self):
        handoff = clean_handoff()
        handoff["evidence"] = []

        result = handoff_gate(handoff)

        self.assertEqual(result["gate_decision"], "block")
        self.assertEqual(result["recommended_action"], "retrieve")
        self.assertTrue(any(violation["code"] == "missing_evidence" for violation in result["violations"]))

    def test_routes_unknown_evidence_source_to_retrieve(self):
        handoff = clean_handoff()
        handoff["evidence"][0]["source_id"] = "unknown-source"
        handoff["evidence"][0]["retrieval_url"] = "aana://evidence/unknown-source"

        result = handoff_gate(handoff)

        self.assertEqual(result["gate_decision"], "block")
        self.assertEqual(result["recommended_action"], "retrieve")
        self.assertFalse(result["evidence_registry_binding"]["valid"])
        self.assertTrue(any(violation["code"] == "unknown_evidence_source" for violation in result["violations"]))

    def test_routes_disallowed_evidence_redaction_to_retrieve(self):
        handoff = clean_handoff()
        handoff["evidence"][0]["redaction_status"] = "unredacted"

        result = handoff_gate(handoff)

        self.assertEqual(result["gate_decision"], "block")
        self.assertEqual(result["recommended_action"], "retrieve")
        self.assertTrue(any(violation["code"] == "disallowed_evidence_redaction_status" for violation in result["violations"]))

    def test_requires_all_recipient_constraint_layers(self):
        handoff = clean_handoff()
        handoff["constraint_map"]["K_B"] = []

        result = handoff_gate(handoff)

        self.assertEqual(result["gate_decision"], "fail")
        self.assertEqual(result["recommended_action"], "defer")
        self.assertTrue(any(violation["code"] == "missing_K_B_constraints" for violation in result["violations"]))


if __name__ == "__main__":
    unittest.main()
