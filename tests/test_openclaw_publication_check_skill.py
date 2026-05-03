import json
import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
SKILL_DIR = ROOT / "examples" / "openclaw" / "aana-publication-check-skill"


class OpenClawPublicationCheckSkillTests(unittest.TestCase):
    def test_manifest_declares_instruction_only_publication_boundaries(self):
        manifest = json.loads((SKILL_DIR / "manifest.json").read_text(encoding="utf-8"))

        self.assertEqual(manifest["slug"], "aana-publication-check")
        self.assertFalse(manifest["bundled_code"])
        self.assertFalse(manifest["executes_commands"])
        self.assertFalse(manifest["writes_files"])
        self.assertFalse(manifest["persists_memory"])
        self.assertTrue(manifest["requires_publication_approval"])
        self.assertTrue(manifest["requires_claim_evidence_check"])
        self.assertTrue(manifest["requires_privacy_redaction_check"])
        self.assertTrue(manifest["requires_asset_permission_check"])
        self.assertTrue(manifest["requires_link_and_download_check"])
        self.assertTrue(manifest["publication_boundary"]["must_not_publish_secrets_or_private_data"])
        self.assertTrue(manifest["publication_boundary"]["must_block_materially_unsupported_or_deceptive_publication"])

    def test_schema_and_example_parse(self):
        schema = json.loads((SKILL_DIR / "schemas" / "publication-check.schema.json").read_text(encoding="utf-8"))
        example = json.loads((SKILL_DIR / "examples" / "redacted-publication-check.json").read_text(encoding="utf-8"))

        for key in schema["required"]:
            self.assertIn(key, example)
        self.assertEqual(example["publication_status"], "needs_review")
        self.assertEqual(example["approval_status"], "required")
        self.assertEqual(example["recommended_action"], "route_to_review")

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
