import importlib.util
import json
import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
PLAN_PATH = ROOT / "examples" / "support_adapter_expansion_plan.json"


def load_script(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


expansion = load_script("validate_support_adapter_expansion", ROOT / "scripts" / "validation" / "validate_support_adapter_expansion.py")


class SupportAdapterExpansionTests(unittest.TestCase):
    def test_expansion_plan_validates_after_enforced_baseline_measurement(self):
        report = expansion.validate_expansion_plan(PLAN_PATH)

        self.assertTrue(report["valid"], report)
        self.assertEqual(set(report["required_candidates"]), expansion.REQUIRED_CANDIDATES)
        self.assertEqual(report["candidate_count"], len(expansion.REQUIRED_CANDIDATES))
        self.assertEqual(report["baseline_status"], "reached")
        self.assertEqual(report["gate_status"], "passed")

    def test_candidates_are_productized_but_not_supported_adapters_yet(self):
        plan = json.loads(PLAN_PATH.read_text(encoding="utf-8"))
        gallery = json.loads((ROOT / "examples" / "adapter_gallery.json").read_text(encoding="utf-8"))
        support_line = gallery["product_lines"]["support"]

        self.assertEqual(set(support_line["later_adapters"]), expansion.REQUIRED_CANDIDATES)
        self.assertEqual(support_line["expansion_plan"], "examples/support_adapter_expansion_plan.json")
        self.assertTrue(expansion.REQUIRED_CANDIDATES.isdisjoint(set(support_line["adapter_ids"])))
        self.assertIn("first enforced support baseline is measured", support_line["expansion_gate"])

        for candidate in plan["candidates"]:
            with self.subTest(candidate=candidate["id"]):
                self.assertEqual(candidate["status"], "expansion_candidate")
                self.assertEqual(candidate["production_status"], "not_supported_expansion_candidate")
                self.assertIn(candidate["risk_tier"], {"high", "strict"})
                self.assertTrue(expansion.REQUIRED_SURFACES.issubset(candidate["supported_surfaces"]))
                self.assertTrue(candidate["evidence_requirements"])
                self.assertTrue(candidate["verifier_behavior"])
                self.assertTrue(candidate["correction_policy"])
                self.assertTrue(candidate["human_review_path"])
                self.assertTrue(candidate["promotion_requirements"])

    def test_expansion_plan_rejects_unmeasured_baseline_gate(self):
        plan = json.loads(PLAN_PATH.read_text(encoding="utf-8"))
        plan["first_enforced_baseline_gate"]["status"] = "pending"

        temp = PLAN_PATH.parent / "_tmp_bad_support_expansion.json"
        try:
            temp.write_text(json.dumps(plan), encoding="utf-8")
            report = expansion.validate_expansion_plan(temp)
        finally:
            temp.unlink(missing_ok=True)

        self.assertFalse(report["valid"])
        self.assertTrue(any("status must be passed" in error for error in report["errors"]))


if __name__ == "__main__":
    unittest.main()
