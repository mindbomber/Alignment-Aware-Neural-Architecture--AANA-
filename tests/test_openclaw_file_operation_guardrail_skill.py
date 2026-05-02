import json
import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
SKILL_DIR = ROOT / "examples" / "openclaw" / "aana-file-operation-guardrail-skill"


class OpenClawFileOperationGuardrailSkillTests(unittest.TestCase):
    def test_manifest_declares_instruction_only_file_operation_boundaries(self):
        manifest = json.loads((SKILL_DIR / "manifest.json").read_text(encoding="utf-8"))

        self.assertEqual(manifest["slug"], "aana-file-operation-guardrail")
        self.assertFalse(manifest["bundled_code"])
        self.assertFalse(manifest["executes_commands"])
        self.assertFalse(manifest["writes_files"])
        self.assertFalse(manifest["persists_memory"])
        self.assertTrue(manifest["requires_user_approval_for_destructive_operations"])
        self.assertTrue(manifest["file_operation_boundary"]["must_confirm_exact_target_scope"])
        self.assertTrue(manifest["file_operation_boundary"]["must_verify_paths_before_destructive_action"])
        self.assertTrue(manifest["file_operation_boundary"]["must_not_publish_or_upload_without_approval"])

    def test_schema_and_example_parse(self):
        schema = json.loads((SKILL_DIR / "schemas" / "file-operation-review.schema.json").read_text(encoding="utf-8"))
        example = json.loads((SKILL_DIR / "examples" / "redacted-file-operation-review.json").read_text(encoding="utf-8"))

        for key in schema["required"]:
            self.assertIn(key, example)
        self.assertEqual(example["operation_type"], "delete")
        self.assertEqual(example["recommended_action"], "ask")
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
