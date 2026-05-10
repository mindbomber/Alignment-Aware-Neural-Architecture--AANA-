import importlib.util
import json
import pathlib
import tempfile
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]


def load_script(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


pilot_plan = load_script("validate_internal_pilot_plan", ROOT / "scripts" / "validation" / "validate_internal_pilot_plan.py")


class InternalPilotPlanTests(unittest.TestCase):
    def test_internal_pilot_plan_requires_shadow_first(self):
        report = pilot_plan.validate_internal_pilot_plan(ROOT / "examples" / "production_deployment_internal_pilot.json")

        self.assertTrue(report["valid"], report)
        self.assertEqual(report["default_phase"], "shadow_mode")
        self.assertEqual(report["phases"], pilot_plan.REQUIRED_PHASES)
        self.assertEqual(report["phase_count"], 5)

    def test_internal_pilot_plan_rejects_full_autonomous_enforcement_start(self):
        manifest = {
            "pilot_rollout": {
                "default_phase": "enforced_support_drafts",
                "autonomous_enforcement_allowed": True,
                "phase_sequence": [
                    {
                        "phase": "enforced_support_drafts",
                        "order": 1,
                        "mode": "enforced",
                        "enforcement": "expanded_support_blocking",
                        "adapters": ["support_reply", "crm_support_reply", "email_send_guardrail"],
                        "required_exit_evidence": ["none"],
                        "promotion_gate": "none",
                    }
                ],
            }
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            path = pathlib.Path(temp_dir) / "bad-pilot.json"
            path.write_text(json.dumps(manifest), encoding="utf-8")

            report = pilot_plan.validate_internal_pilot_plan(path)

        self.assertFalse(report["valid"])
        self.assertTrue(any("default_phase must be shadow_mode" in error for error in report["errors"]))
        self.assertTrue(any("autonomous_enforcement_allowed must be false" in error for error in report["errors"]))
        self.assertTrue(any("phase_sequence must be ordered" in error for error in report["errors"]))


if __name__ == "__main__":
    unittest.main()
