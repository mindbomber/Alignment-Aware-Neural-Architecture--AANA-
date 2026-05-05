import json
import pathlib
import unittest

from eval_pipeline import agent_api, evidence, workflow_contract


ROOT = pathlib.Path(__file__).resolve().parents[1]


class WorkflowContractHardeningTests(unittest.TestCase):
    def valid_request(self):
        return {
            "contract_version": workflow_contract.WORKFLOW_CONTRACT_VERSION,
            "workflow_id": "workflow-hardening-valid-001",
            "adapter": "research_summary",
            "request": "Write a concise research brief. Use only Source A.",
            "candidate": "AANA improves productivity by 40% for all teams [Source C].",
            "evidence": ["Source A: AANA makes constraints explicit."],
            "constraints": ["Do not invent citations."],
            "allowed_actions": ["accept", "revise", "defer", "refuse"],
        }

    def test_batch_runtime_failure_isolated_per_item(self):
        batch = {
            "contract_version": workflow_contract.WORKFLOW_CONTRACT_VERSION,
            "batch_id": "workflow-hardening-batch-001",
            "requests": [
                self.valid_request(),
                {
                    "workflow_id": "workflow-hardening-unknown-adapter-001",
                    "adapter": "unknown_adapter",
                    "request": "Check this proposed action.",
                    "candidate": "Proceed.",
                    "evidence": ["Source A: verified."],
                    "allowed_actions": ["accept", "revise", "defer"],
                },
            ],
        }

        result = agent_api.check_workflow_batch(batch)

        self.assertEqual(result["summary"]["total"], 2)
        self.assertEqual(result["summary"]["passed"], 1)
        self.assertEqual(result["summary"]["failed"], 1)
        self.assertEqual(result["results"][0]["gate_decision"], "pass")
        self.assertEqual(result["results"][1]["gate_decision"], "fail")
        self.assertEqual(result["results"][1]["recommended_action"], "defer")
        self.assertTrue(any(item["code"] == "workflow_item_error" for item in result["results"][1]["violations"]))
        self.assertIn("workflow_item_error", result["results"][1]["aix"]["hard_blockers"])

    def test_batch_failure_never_recommends_direct_accept(self):
        batch = {
            "contract_version": workflow_contract.WORKFLOW_CONTRACT_VERSION,
            "batch_id": "workflow-hardening-batch-accept-only",
            "requests": [
                {
                    "workflow_id": "workflow-hardening-accept-only-001",
                    "adapter": "unknown_adapter",
                    "request": "Check this proposed action.",
                    "candidate": "Proceed.",
                    "evidence": ["Source A: verified."],
                    "allowed_actions": ["accept"],
                }
            ],
        }

        result = agent_api.check_workflow_batch(batch)

        self.assertEqual(result["summary"]["failed"], 1)
        self.assertEqual(result["results"][0]["gate_decision"], "fail")
        self.assertEqual(result["results"][0]["recommended_action"], "defer")
        self.assertTrue(any(item["code"] == "no_safe_allowed_action" for item in result["results"][0]["violations"]))
        self.assertEqual(result["results"][0]["aix"]["decision"], "refuse")

    def test_batch_evidence_validation_requires_structured_items(self):
        registry = evidence.load_registry(ROOT / "examples" / "evidence_registry.json")
        batch = {
            "contract_version": workflow_contract.WORKFLOW_CONTRACT_VERSION,
            "batch_id": "workflow-hardening-evidence-001",
            "requests": [self.valid_request()],
        }

        report = agent_api.validate_workflow_batch_evidence(batch, registry, require_structured=True)

        self.assertFalse(report["valid"])
        self.assertEqual(report["reports"][0]["index"], 0)
        self.assertTrue(any(issue["path"] == "$.requests[0].evidence[0]" for issue in report["issues"]))

    def test_batch_evidence_validation_checks_source_registry(self):
        registry = evidence.load_registry(ROOT / "examples" / "evidence_registry.json")
        good_request = self.valid_request()
        good_request["evidence"] = [
            {
                "source_id": "source-a",
                "retrieved_at": "2026-05-05T00:00:00Z",
                "trust_tier": "verified",
                "redaction_status": "public",
                "text": "Source A: AANA makes constraints explicit.",
            }
        ]
        bad_request = dict(good_request)
        bad_request["workflow_id"] = "workflow-hardening-bad-source-001"
        bad_request["evidence"] = [dict(good_request["evidence"][0], source_id="unknown-source")]
        batch = {
            "contract_version": workflow_contract.WORKFLOW_CONTRACT_VERSION,
            "batch_id": "workflow-hardening-evidence-002",
            "requests": [good_request, bad_request],
        }

        report = agent_api.validate_workflow_batch_evidence(batch, registry, require_structured=True)

        self.assertFalse(report["valid"])
        self.assertTrue(report["reports"][0]["valid"])
        self.assertFalse(report["reports"][1]["valid"])
        self.assertTrue(any(issue["path"] == "$.requests[1].evidence[0].source_id" for issue in report["issues"]))

    def test_canonical_workflow_examples_validate(self):
        catalog = json.loads((ROOT / "examples" / "workflow_contract_examples.json").read_text(encoding="utf-8"))

        self.assertEqual(catalog["contract_version"], workflow_contract.WORKFLOW_CONTRACT_VERSION)
        self.assertGreaterEqual(len(catalog["adapter_families"]), 3)
        for family in catalog["adapter_families"]:
            self.assertTrue(family["examples"], family)
            for example in family["examples"]:
                request = json.loads((ROOT / example["workflow_file"]).read_text(encoding="utf-8"))
                report = workflow_contract.validate_workflow_request(request)
                self.assertTrue(report["valid"], (example, report))
                self.assertEqual(request["adapter"], example["adapter"])


if __name__ == "__main__":
    unittest.main()
