import json
import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
SKILL_DIR = ROOT / "examples" / "openclaw" / "aana-email-send-guardrail-skill"


class OpenClawEmailSendGuardrailSkillTests(unittest.TestCase):
    def test_manifest_declares_instruction_only_email_boundaries(self):
        manifest = json.loads((SKILL_DIR / "manifest.json").read_text(encoding="utf-8"))

        self.assertEqual(manifest["slug"], "aana-email-send-guardrail")
        self.assertFalse(manifest["bundled_code"])
        self.assertFalse(manifest["executes_commands"])
        self.assertFalse(manifest["writes_files"])
        self.assertFalse(manifest["persists_memory"])
        self.assertTrue(manifest["requires_recipient_verification"])
        self.assertTrue(manifest["requires_send_approval"])
        self.assertTrue(manifest["requires_tone_check"])
        self.assertTrue(manifest["requires_private_data_check"])
        self.assertTrue(manifest["requires_attachment_check"])
        self.assertTrue(manifest["requires_claim_evidence_check"])
        self.assertTrue(manifest["email_send_boundary"]["must_not_treat_draft_approval_as_send_approval"])
        self.assertTrue(manifest["email_send_boundary"]["must_block_unsafe_or_unauthorized_send"])

    def test_schema_and_example_parse(self):
        schema = json.loads((SKILL_DIR / "schemas" / "email-send-guardrail.schema.json").read_text(encoding="utf-8"))
        example = json.loads((SKILL_DIR / "examples" / "redacted-email-send-guardrail.json").read_text(encoding="utf-8"))

        for key in schema["required"]:
            self.assertIn(key, example)
        self.assertEqual(example["email_action"], "send")
        self.assertEqual(example["approval_status"], "required")
        self.assertEqual(example["recommended_action"], "request_approval")

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
