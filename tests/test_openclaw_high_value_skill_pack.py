import json
import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
OPENCLAW_DIR = ROOT / "examples" / "openclaw"

SKILLS = {
    "aana-calendar-scheduling-guardrail-skill": {
        "slug": "aana-calendar-scheduling-guardrail",
        "schema": "calendar-scheduling-guardrail.schema.json",
        "example": "redacted-calendar-scheduling-guardrail.json",
        "required_flag": "requires_calendar_change_approval",
        "risk_key": "calendar_risks",
        "expected_action": "request_approval",
    },
    "aana-message-send-guardrail-skill": {
        "slug": "aana-message-send-guardrail",
        "schema": "message-send-guardrail.schema.json",
        "example": "redacted-message-send-guardrail.json",
        "required_flag": "requires_send_approval",
        "risk_key": "message_risks",
        "expected_action": "request_approval",
    },
    "aana-ticket-update-checker-skill": {
        "slug": "aana-ticket-update-checker",
        "schema": "ticket-update-checker.schema.json",
        "example": "redacted-ticket-update-checker.json",
        "required_flag": "requires_visibility_check",
        "risk_key": "ticket_risks",
        "expected_action": "request_approval",
    },
    "aana-data-export-guardrail-skill": {
        "slug": "aana-data-export-guardrail",
        "schema": "data-export-guardrail.schema.json",
        "example": "redacted-data-export-guardrail.json",
        "required_flag": "requires_export_approval",
        "risk_key": "export_risks",
        "expected_action": "route_to_review",
    },
    "aana-release-readiness-check-skill": {
        "slug": "aana-release-readiness-check",
        "schema": "release-readiness-check.schema.json",
        "example": "redacted-release-readiness-check.json",
        "required_flag": "requires_release_approval",
        "risk_key": "release_risks",
        "expected_action": "request_approval",
    },
}


class OpenClawHighValueSkillPackTests(unittest.TestCase):
    def test_manifests_declare_instruction_only_boundaries(self):
        for skill_dir, expected in SKILLS.items():
            with self.subTest(skill=skill_dir):
                manifest = json.loads((OPENCLAW_DIR / skill_dir / "manifest.json").read_text(encoding="utf-8"))

                self.assertEqual(manifest["slug"], expected["slug"])
                self.assertFalse(manifest["bundled_code"])
                self.assertFalse(manifest["executes_commands"])
                self.assertFalse(manifest["writes_files"])
                self.assertFalse(manifest["persists_memory"])
                self.assertTrue(manifest[expected["required_flag"]])

    def test_schema_and_example_parse(self):
        for skill_dir, expected in SKILLS.items():
            with self.subTest(skill=skill_dir):
                root = OPENCLAW_DIR / skill_dir
                schema = json.loads((root / "schemas" / expected["schema"]).read_text(encoding="utf-8"))
                example = json.loads((root / "examples" / expected["example"]).read_text(encoding="utf-8"))

                for key in schema["required"]:
                    self.assertIn(key, example)
                self.assertIn(expected["risk_key"], schema["properties"])
                self.assertIn("blocker_reason", schema["properties"])
                self.assertIn("safe_alternative", schema["properties"])
                self.assertIn(expected["risk_key"], example)
                self.assertIn("blocker_reason", example)
                self.assertIn("safe_alternative", example)
                self.assertEqual(example["recommended_action"], expected["expected_action"])

    def test_skill_instructions_include_operational_depth(self):
        required_sections = [
            "## Required Checks",
            "## Review Payload",
            "## Decision Rule",
            "## Output Pattern",
        ]

        for skill_dir in SKILLS:
            with self.subTest(skill=skill_dir):
                skill_text = (OPENCLAW_DIR / skill_dir / "SKILL.md").read_text(encoding="utf-8")
                for section in required_sections:
                    self.assertIn(section, skill_text)
                self.assertGreaterEqual(skill_text.count("- "), 30)

    def test_skill_packages_avoid_executable_and_raw_network_patterns(self):
        blocked_phrases = [
            "python scripts/",
            "pip install",
            "http://127.",
            "https://",
            "execute command",
        ]

        for skill_dir in SKILLS:
            with self.subTest(skill=skill_dir):
                texts = []
                for path in (OPENCLAW_DIR / skill_dir).rglob("*"):
                    if path.is_file() and path.suffix in {".md", ".json"}:
                        texts.append(path.read_text(encoding="utf-8").lower())
                text = "\n".join(texts)

                for phrase in blocked_phrases:
                    self.assertNotIn(phrase, text)


if __name__ == "__main__":
    unittest.main()
