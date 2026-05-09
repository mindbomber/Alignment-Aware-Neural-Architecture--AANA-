import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from eval_pipeline.hf_dataset_registry import validate_hf_dataset_registry


ROOT = Path(__file__).resolve().parents[1]


def valid_registry():
    return {
        "schema_version": "0.1",
        "policy": {
            "allowed_uses": ["calibration", "heldout_validation", "external_reporting"],
            "strategic_primary_uses": [
                "threshold_calibration",
                "false_positive_reduction",
                "heldout_generalization_testing",
                "adapter_family_proof",
            ],
            "target_capabilities": [
                "privacy_pii_recall",
                "grounded_qa_hallucination_detection",
                "unsafe_tool_call_gating",
                "authorization_state_detection",
                "public_vs_private_read_classification",
                "ask_defer_refuse_route_quality",
            ],
            "never_use_same_split_for_tuning_and_public_claims": True,
        },
        "strategic_objectives": [
            {
                "id": "privacy_pii_recall",
                "allowed_use": "calibration",
                "adapter_families": ["privacy"],
                "target_metrics": ["pii_recall"],
                "status": "planned",
            },
            {
                "id": "grounded_qa_hallucination_detection",
                "allowed_use": "calibration",
                "adapter_families": ["research_grounding"],
                "target_metrics": ["unsupported_claim_recall"],
                "status": "planned",
            },
            {
                "id": "unsafe_tool_call_gating",
                "allowed_use": "calibration",
                "adapter_families": ["agent_tool_gate"],
                "target_metrics": ["unsafe_action_recall"],
                "status": "planned",
            },
            {
                "id": "authorization_state_detection",
                "allowed_use": "heldout_validation",
                "adapter_families": ["agent_tool_gate"],
                "target_metrics": ["authorization_state_accuracy"],
                "status": "planned",
            },
            {
                "id": "public_vs_private_read_classification",
                "allowed_use": "heldout_validation",
                "adapter_families": ["agent_tool_gate"],
                "target_metrics": ["public_read_safe_allow_rate"],
                "status": "planned",
            },
            {
                "id": "ask_defer_refuse_route_quality",
                "allowed_use": "heldout_validation",
                "adapter_families": ["agent_tool_gate"],
                "target_metrics": ["route_accuracy"],
                "status": "planned",
            },
        ],
        "implementation_tasks": [
            {"task": "Create registry.", "status": "completed"},
        ],
        "tracked_todos": [
            {
                "id": "governance_compliance_hf_dataset_search",
                "task": "Search for governance/compliance HF datasets.",
                "status": "planned",
                "reason": "Current coverage is repo-heldout fixture based.",
                "acceptance_criteria": ["Register one split-safe dataset."],
            }
        ],
        "datasets": [
            {
                "dataset_name": "org/example",
                "license": "apache-2.0",
                "task_type": "agent_tool_calling",
                "adapter_families": ["agent_tool_gate"],
                "split_uses": [
                    {
                        "config": "default",
                        "split": "train",
                        "allowed_use": "calibration",
                        "split_purpose": "tuning",
                        "adapter_family": "agent_tool_gate",
                    },
                    {
                        "config": "default",
                        "split": "test",
                        "allowed_use": "external_reporting",
                        "split_purpose": "public_claim",
                        "adapter_family": "agent_tool_gate",
                    },
                ],
            }
        ],
    }


class HFDatasetRegistryTests(unittest.TestCase):
    def test_current_registry_is_valid(self):
        registry = json.loads((ROOT / "examples" / "hf_dataset_validation_registry.json").read_text(encoding="utf-8"))
        report = validate_hf_dataset_registry(registry)

        self.assertTrue(report["valid"], report["issues"])
        self.assertGreaterEqual(report["dataset_count"], 5)
        self.assertGreater(report["split_use_counts"]["calibration"], 0)
        self.assertGreater(report["split_use_counts"]["heldout_validation"], 0)
        self.assertGreater(report["split_use_counts"]["external_reporting"], 0)

    def test_requires_strategic_hf_dataset_targets(self):
        registry = valid_registry()
        registry["policy"]["target_capabilities"].remove("authorization_state_detection")
        report = validate_hf_dataset_registry(registry)

        self.assertFalse(report["valid"])
        self.assertTrue(any("target capabilities" in issue["message"] for issue in report["issues"]))

    def test_requires_objective_for_each_target_capability(self):
        registry = valid_registry()
        registry["strategic_objectives"] = [
            objective
            for objective in registry["strategic_objectives"]
            if objective["id"] != "public_vs_private_read_classification"
        ]
        report = validate_hf_dataset_registry(registry)

        self.assertFalse(report["valid"])
        self.assertTrue(any("Missing strategic objectives" in issue["message"] for issue in report["issues"]))

    def test_blocks_same_split_for_calibration_and_external_reporting(self):
        registry = valid_registry()
        registry["datasets"][0]["split_uses"][1]["split"] = "train"
        report = validate_hf_dataset_registry(registry)

        self.assertFalse(report["valid"])
        self.assertTrue(any("cannot be used for both calibration and external_reporting" in issue["message"] for issue in report["issues"]))

    def test_blocks_same_split_for_tuning_and_public_claims_even_with_different_allowed_use(self):
        registry = valid_registry()
        registry["datasets"][0]["split_uses"][1]["split"] = "train"
        registry["datasets"][0]["split_uses"][1]["allowed_use"] = "heldout_validation"
        report = validate_hf_dataset_registry(registry)

        self.assertFalse(report["valid"])
        self.assertTrue(any("cannot be used for both tuning and public claims" in issue["message"] for issue in report["issues"]))

    def test_blocks_same_split_for_calibration_and_heldout_validation(self):
        registry = valid_registry()
        registry["datasets"][0]["split_uses"][1]["split"] = "train"
        registry["datasets"][0]["split_uses"][1]["allowed_use"] = "heldout_validation"
        registry["datasets"][0]["split_uses"][1]["split_purpose"] = "validation"
        report = validate_hf_dataset_registry(registry)

        self.assertFalse(report["valid"])
        self.assertTrue(any("calibration and heldout_validation" in issue["message"] for issue in report["issues"]))

    def test_requires_governance_compliance_dataset_search_todo(self):
        registry = valid_registry()
        registry["tracked_todos"] = []
        report = validate_hf_dataset_registry(registry)

        self.assertFalse(report["valid"])
        self.assertTrue(any("governance_compliance_hf_dataset_search" in issue["message"] for issue in report["issues"]))

    def test_blocks_incomplete_task_list(self):
        registry = valid_registry()
        registry["implementation_tasks"][0]["status"] = "pending"
        report = validate_hf_dataset_registry(registry)

        self.assertFalse(report["valid"])
        self.assertTrue(any(issue["path"].endswith("status") for issue in report["issues"]))

    def test_cli_validates_registry(self):
        with tempfile.TemporaryDirectory() as directory:
            registry_path = Path(directory) / "registry.json"
            registry_path.write_text(json.dumps(valid_registry()), encoding="utf-8")
            completed = subprocess.run(
                [sys.executable, "scripts/validate_hf_dataset_registry.py", "--registry", str(registry_path)],
                cwd=ROOT,
                text=True,
                capture_output=True,
            )

        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        self.assertIn("pass -- datasets=1", completed.stdout)


if __name__ == "__main__":
    unittest.main()
