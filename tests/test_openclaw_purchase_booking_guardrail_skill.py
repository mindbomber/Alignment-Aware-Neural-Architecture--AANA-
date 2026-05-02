import json
import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
SKILL_DIR = ROOT / "examples" / "openclaw" / "aana-purchase-booking-guardrail-skill"


class OpenClawPurchaseBookingGuardrailSkillTests(unittest.TestCase):
    def test_manifest_declares_instruction_only_purchase_booking_boundaries(self):
        manifest = json.loads((SKILL_DIR / "manifest.json").read_text(encoding="utf-8"))

        self.assertEqual(manifest["slug"], "aana-purchase-booking-guardrail")
        self.assertFalse(manifest["bundled_code"])
        self.assertFalse(manifest["executes_commands"])
        self.assertFalse(manifest["writes_files"])
        self.assertFalse(manifest["persists_memory"])
        self.assertTrue(manifest["requires_user_approval_for_financial_commitments"])
        self.assertTrue(manifest["purchase_booking_boundary"]["must_confirm_exact_commitment_before_submission"])
        self.assertTrue(manifest["purchase_booking_boundary"]["must_verify_total_price_and_fees"])
        self.assertTrue(manifest["purchase_booking_boundary"]["may_not_spend_money_without_explicit_approval"])

    def test_schema_and_example_parse(self):
        schema = json.loads((SKILL_DIR / "schemas" / "purchase-booking-review.schema.json").read_text(encoding="utf-8"))
        example = json.loads((SKILL_DIR / "examples" / "redacted-purchase-booking-review.json").read_text(encoding="utf-8"))

        for key in schema["required"]:
            self.assertIn(key, example)
        self.assertEqual(example["action_type"], "book")
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
