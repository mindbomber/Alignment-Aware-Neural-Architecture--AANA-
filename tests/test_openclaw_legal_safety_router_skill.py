import json
import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
SKILL_DIR = ROOT / "examples" / "openclaw" / "aana-legal-safety-router-skill"


class OpenClawLegalSafetyRouterSkillTests(unittest.TestCase):
    def test_manifest_declares_instruction_only_legal_safety_boundaries(self):
        manifest = json.loads((SKILL_DIR / "manifest.json").read_text(encoding="utf-8"))

        self.assertEqual(manifest["slug"], "aana-legal-safety-router")
        self.assertFalse(manifest["bundled_code"])
        self.assertFalse(manifest["executes_commands"])
        self.assertFalse(manifest["writes_files"])
        self.assertFalse(manifest["persists_memory"])
        self.assertTrue(manifest["requires_jurisdiction_caveats_for_legal_information"])
        self.assertTrue(manifest["legal_safety_boundary"]["must_not_create_attorney_client_relationship"])
        self.assertTrue(manifest["legal_safety_boundary"]["must_not_invent_statutes_cases_deadlines_or_rights"])
        self.assertTrue(manifest["legal_safety_boundary"]["must_minimize_private_legal_data"])

    def test_schema_and_example_parse(self):
        schema = json.loads((SKILL_DIR / "schemas" / "legal-safety-review.schema.json").read_text(encoding="utf-8"))
        example = json.loads((SKILL_DIR / "examples" / "redacted-legal-safety-review.json").read_text(encoding="utf-8"))

        for key in schema["required"]:
            self.assertIn(key, example)
        self.assertEqual(example["legal_context"], "housing")
        self.assertEqual(example["recommended_action"], "revise")
        self.assertEqual(example["jurisdiction_status"], "missing")

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
