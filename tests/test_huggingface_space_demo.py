import importlib.util
import json
import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
SPACE_APP = ROOT / "examples" / "huggingface_space" / "app.py"


def load_space_app():
    spec = importlib.util.spec_from_file_location("aana_huggingface_space_app", SPACE_APP)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class HuggingFaceSpaceDemoTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.space = load_space_app()

    def test_examples_cover_accept_ask_defer_refuse(self):
        observed = {}
        for name in self.space.EXAMPLE_EVENTS:
            _, compact_json, proof_json, _ = self.space.check_event(self.space.example_event(name))
            compact = json.loads(compact_json)
            proof = json.loads(proof_json)
            observed[name] = compact["route"]
            if compact["route"] == "accept":
                self.assertEqual(proof["synthetic_executor_call_count_after"], 1)
                self.assertFalse(proof["blocked_tool_non_execution_proven"])
            else:
                self.assertEqual(proof["synthetic_executor_call_count_after"], 0)
                self.assertTrue(proof["blocked_tool_non_execution_proven"])

        self.assertEqual(set(observed.values()), {"accept", "ask", "defer", "refuse"})

    def test_compact_summary_exposes_public_demo_fields(self):
        _, compact_json, proof_json, _ = self.space.check_event(
            self.space.example_event("Blocked: write missing confirmation")
        )
        compact = json.loads(compact_json)
        proof = json.loads(proof_json)

        for field in [
            "route",
            "aix_score",
            "hard_blockers",
            "missing_evidence",
            "authorization_state",
            "audit_safe_log_event",
            "blocked_tool_non_execution_proven",
        ]:
            self.assertIn(field, compact)
        self.assertEqual(compact["route"], "ask")
        self.assertEqual(proof["synthetic_executor_call_count_after"], 0)

    def test_backward_compatible_json_helper_returns_full_decision(self):
        full = json.loads(self.space.check_json_event(self.space.example_event("Blocked: private read missing auth")))

        self.assertIn("architecture_decision", full)
        self.assertEqual(full["architecture_decision"]["route"], "defer")


if __name__ == "__main__":
    unittest.main()
