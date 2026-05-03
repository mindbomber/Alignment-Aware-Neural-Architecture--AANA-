import json
import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
SKILL_DIR = ROOT / "examples" / "openclaw" / "aana-meeting-summary-checker-skill"


class OpenClawMeetingSummaryCheckerSkillTests(unittest.TestCase):
    def test_manifest_declares_instruction_only_meeting_boundaries(self):
        manifest = json.loads((SKILL_DIR / "manifest.json").read_text(encoding="utf-8"))

        self.assertEqual(manifest["slug"], "aana-meeting-summary-checker")
        self.assertFalse(manifest["bundled_code"])
        self.assertFalse(manifest["executes_commands"])
        self.assertFalse(manifest["writes_files"])
        self.assertFalse(manifest["persists_memory"])
        self.assertTrue(manifest["requires_transcript_or_evidence_check"])
        self.assertTrue(manifest["requires_action_item_check"])
        self.assertTrue(manifest["requires_owner_check"])
        self.assertTrue(manifest["requires_date_check"])
        self.assertTrue(manifest["requires_claim_attribution_check"])
        self.assertTrue(manifest["requires_privacy_redaction_check"])
        self.assertTrue(manifest["meeting_summary_boundary"]["must_not_invent_decisions_or_commitments"])
        self.assertTrue(manifest["meeting_summary_boundary"]["must_block_unsupported_or_unauthorized_sharing"])

    def test_schema_and_example_parse(self):
        schema = json.loads((SKILL_DIR / "schemas" / "meeting-summary-checker.schema.json").read_text(encoding="utf-8"))
        example = json.loads((SKILL_DIR / "examples" / "redacted-meeting-summary-checker.json").read_text(encoding="utf-8"))

        for key in schema["required"]:
            self.assertIn(key, example)
        self.assertEqual(example["summary_status"], "needs_owner_confirmation")
        self.assertEqual(example["owner_status"], "unclear")
        self.assertEqual(example["recommended_action"], "request_confirmation")

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
