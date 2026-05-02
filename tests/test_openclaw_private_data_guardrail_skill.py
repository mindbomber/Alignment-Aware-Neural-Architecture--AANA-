import json
import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
SKILL_DIR = ROOT / "examples" / "openclaw" / "aana-private-data-guardrail-skill"


class OpenClawPrivateDataGuardrailSkillTests(unittest.TestCase):
    def test_manifest_declares_instruction_only_privacy_boundaries(self):
        manifest = json.loads((SKILL_DIR / "manifest.json").read_text(encoding="utf-8"))

        self.assertEqual(manifest["slug"], "aana-private-data-guardrail")
        self.assertFalse(manifest["bundled_code"])
        self.assertFalse(manifest["executes_commands"])
        self.assertFalse(manifest["writes_files"])
        self.assertFalse(manifest["persists_memory"])
        self.assertTrue(manifest["privacy_boundary"]["must_minimize_private_data"])
        self.assertTrue(manifest["privacy_boundary"]["must_not_expose_secrets"])
        self.assertTrue(manifest["privacy_boundary"]["must_ask_when_authorization_is_unclear"])

    def test_schema_and_example_parse(self):
        schema = json.loads((SKILL_DIR / "schemas" / "private-data-review.schema.json").read_text(encoding="utf-8"))
        example = json.loads((SKILL_DIR / "examples" / "redacted-private-data-review.json").read_text(encoding="utf-8"))

        for key in schema["required"]:
            self.assertIn(key, example)
        self.assertEqual(example["recommended_action"], "revise")
        self.assertEqual(example["authorization_status"], "unclear")

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
