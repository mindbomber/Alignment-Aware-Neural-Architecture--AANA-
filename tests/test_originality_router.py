import json
import pathlib
import sys
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "eval_pipeline"))

from materialize_originality_router import clone_as_routed, routed_model, source_condition


class OriginalityRouterTests(unittest.TestCase):
    def test_product_and_theory_route_to_aana(self):
        self.assertEqual(source_condition("originality_product"), "originality_aana")
        self.assertEqual(source_condition("originality_theory"), "originality_aana")

    def test_other_originality_types_route_to_baseline(self):
        self.assertEqual(source_condition("originality_plan"), "baseline")
        self.assertEqual(source_condition("originality_hypothesis"), "baseline")

    def test_clone_as_routed_updates_model_condition_and_trace(self):
        row = {
            "id": "originality_001",
            "task_type": "originality_product",
            "model": "example-model",
            "correction": "originality_aana",
        }

        routed = clone_as_routed(row, "example-model")
        trace = json.loads(routed["aana_trace"])

        self.assertEqual(routed["model"], routed_model("example-model"))
        self.assertEqual(routed["correction"], "originality_routed")
        self.assertEqual(trace["route"]["routed_to"], "originality_aana")
        self.assertEqual(row["correction"], "originality_aana")


if __name__ == "__main__":
    unittest.main()
