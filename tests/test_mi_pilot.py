import json
import tempfile
import unittest
from pathlib import Path

from eval_pipeline.mi_audit import load_mi_audit_jsonl, validate_mi_audit_records
from eval_pipeline.mi_pilot import (
    research_citation_pilot_handoffs,
    run_research_citation_mi_pilot,
    write_research_citation_mi_pilot,
)


class MIPilotTests(unittest.TestCase):
    def test_research_citation_pilot_builds_real_workflow_handoffs(self):
        handoffs = research_citation_pilot_handoffs()

        self.assertEqual(len(handoffs), 3)
        self.assertEqual(handoffs[0]["metadata"]["boundary_type"], "tool_to_agent")
        self.assertEqual(handoffs[1]["metadata"]["boundary_type"], "agent_to_agent")
        self.assertEqual(handoffs[2]["metadata"]["boundary_type"], "agent_to_tool")
        self.assertTrue(all(handoff["evidence"] for handoff in handoffs))

    def test_research_citation_pilot_runs_full_mi_gate(self):
        result = run_research_citation_mi_pilot()
        batch = result["mi_batch"]

        self.assertEqual(result["pilot_id"], "research_citation_mi_pilot")
        self.assertEqual(result["candidate_workflow"], "research/citation workflow")
        self.assertFalse(result["accepted"])
        self.assertEqual(result["recommended_action"], "revise")
        self.assertEqual(batch["summary"]["total"], 3)
        self.assertGreater(batch["propagated_risk"]["risk_count"], 0)
        self.assertGreater(batch["shared_correction"]["action_count"], 0)
        self.assertEqual(len(batch["mi_audit_records"]), 3)

    def test_pilot_routes_downstream_dependency_to_upstream_revision(self):
        result = run_research_citation_mi_pilot()
        actions = result["mi_batch"]["shared_correction"]["actions"]

        upstream_revisions = [
            action
            for action in actions
            if action["action"] == "revise_upstream_output"
            and action["source"] == "uncertain_output_became_premise"
        ]
        self.assertEqual(len(upstream_revisions), 1)
        self.assertIn("research-agent-to-citation-guard", upstream_revisions[0]["target_handoff_id"])
        self.assertIn("publication-agent-to-publication-check", upstream_revisions[0]["requested_by_handoff_id"])

    def test_write_research_citation_pilot_outputs_artifacts(self):
        with tempfile.TemporaryDirectory() as directory:
            payload = write_research_citation_mi_pilot(directory)
            paths = {key: Path(value) for key, value in payload["paths"].items()}
            result = json.loads(paths["pilot_result"].read_text(encoding="utf-8"))
            handoffs = json.loads(paths["pilot_handoffs"].read_text(encoding="utf-8"))
            audit_records = load_mi_audit_jsonl(paths["mi_audit_jsonl"])
            dashboard = json.loads(paths["mi_dashboard"].read_text(encoding="utf-8"))

        self.assertEqual(result["mi_pilot_version"], "0.1")
        self.assertEqual(len(handoffs["handoffs"]), 3)
        self.assertTrue(validate_mi_audit_records(audit_records)["valid"])
        self.assertEqual(dashboard["source"], "research_citation_mi_pilot")


if __name__ == "__main__":
    unittest.main()
