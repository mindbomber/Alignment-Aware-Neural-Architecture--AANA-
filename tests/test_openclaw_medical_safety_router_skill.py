import json
import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
SKILL_DIR = ROOT / "examples" / "openclaw" / "aana-medical-safety-router-skill"


class OpenClawMedicalSafetyRouterSkillTests(unittest.TestCase):
    def test_manifest_declares_instruction_only_medical_safety_boundaries(self):
        manifest = json.loads((SKILL_DIR / "manifest.json").read_text(encoding="utf-8"))

        self.assertEqual(manifest["slug"], "aana-medical-safety-router")
        self.assertFalse(manifest["bundled_code"])
        self.assertFalse(manifest["executes_commands"])
        self.assertFalse(manifest["writes_files"])
        self.assertFalse(manifest["persists_memory"])
        self.assertTrue(manifest["requires_emergency_routing_for_urgent_warning_signs"])
        self.assertTrue(manifest["medical_safety_boundary"]["must_not_diagnose_from_chat"])
        self.assertTrue(manifest["medical_safety_boundary"]["must_route_emergencies_to_immediate_care"])
        self.assertTrue(manifest["medical_safety_boundary"]["must_minimize_private_health_data"])

    def test_schema_and_example_parse(self):
        schema = json.loads((SKILL_DIR / "schemas" / "medical-safety-review.schema.json").read_text(encoding="utf-8"))
        example = json.loads((SKILL_DIR / "examples" / "redacted-medical-safety-review.json").read_text(encoding="utf-8"))

        for key in schema["required"]:
            self.assertIn(key, example)
        self.assertEqual(example["risk_level"], "emergency")
        self.assertEqual(example["recommended_action"], "emergency_route")
        self.assertEqual(example["diagnosis_overclaim_status"], "overclaim_detected")

    def test_skill_package_avoids_executable_and_raw_network_patterns(self):
        texts = []
        for path in SKILL_DIR.rglob("*"):
            if path.is_file() and path.suffix in {".md", ".json"}:
                texts.append(path.read_text(encoding="utf-8").lower())
        text = "\n".join(texts)

        blocked_phrases = [
            "python scripts/",
            "pip install",
            "http://127.",
            "https://",
            "execute command",
        ]
        for phrase in blocked_phrases:
            self.assertNotIn(phrase, text)


if __name__ == "__main__":
    unittest.main()
