import json
import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
SKILL_DIR = ROOT / "examples" / "openclaw" / "aana-tool-use-gate-skill"


class OpenClawToolUseGateSkillTests(unittest.TestCase):
    def test_manifest_declares_instruction_only_tool_use_boundaries(self):
        manifest = json.loads((SKILL_DIR / "manifest.json").read_text(encoding="utf-8"))

        self.assertEqual(manifest["slug"], "aana-tool-use-gate")
        self.assertFalse(manifest["bundled_code"])
        self.assertFalse(manifest["executes_commands"])
        self.assertFalse(manifest["writes_files"])
        self.assertFalse(manifest["persists_memory"])
        self.assertTrue(manifest["requires_tool_necessity_check"])
        self.assertTrue(manifest["tool_use_boundary"]["must_check_tool_necessity"])
        self.assertTrue(manifest["tool_use_boundary"]["must_verify_user_authorization"])
        self.assertTrue(manifest["tool_use_boundary"]["may_not_use_tools_for_unauthorized_access_or_exfiltration"])

    def test_schema_and_example_parse(self):
        schema = json.loads((SKILL_DIR / "schemas" / "tool-use-review.schema.json").read_text(encoding="utf-8"))
        example = json.loads((SKILL_DIR / "examples" / "redacted-tool-use-review.json").read_text(encoding="utf-8"))

        for key in schema["required"]:
            self.assertIn(key, example)
        self.assertEqual(example["recommended_action"], "ask")
        self.assertEqual(example["authorization_status"], "approval_required")
        self.assertIn("external_send", example["risk_classes"])

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
