import json
import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
SKILL_DIR = ROOT / "examples" / "openclaw" / "aana-support-reply-guardrail-skill"


class OpenClawSupportReplyGuardrailSkillTests(unittest.TestCase):
    def test_manifest_declares_instruction_only_support_reply_boundaries(self):
        manifest = json.loads((SKILL_DIR / "manifest.json").read_text(encoding="utf-8"))

        self.assertEqual(manifest["slug"], "aana-support-reply-guardrail")
        self.assertFalse(manifest["bundled_code"])
        self.assertFalse(manifest["executes_commands"])
        self.assertFalse(manifest["writes_files"])
        self.assertFalse(manifest["persists_memory"])
        self.assertTrue(manifest["requires_user_approval_for_refund_or_credit_promises"])
        self.assertTrue(manifest["support_reply_boundary"]["must_not_invent_account_facts"])
        self.assertTrue(manifest["support_reply_boundary"]["must_not_promise_refunds_without_authorization"])
        self.assertTrue(manifest["support_reply_boundary"]["must_minimize_private_data"])

    def test_schema_and_example_parse(self):
        schema = json.loads((SKILL_DIR / "schemas" / "support-reply-review.schema.json").read_text(encoding="utf-8"))
        example = json.loads((SKILL_DIR / "examples" / "redacted-support-reply-review.json").read_text(encoding="utf-8"))

        for key in schema["required"]:
            self.assertIn(key, example)
        self.assertEqual(example["support_context"], "refund")
        self.assertEqual(example["recommended_action"], "revise")
        self.assertEqual(example["refund_or_policy_promise_status"], "promise_detected")

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
