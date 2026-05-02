import json
import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
SKILL_DIR = ROOT / "examples" / "openclaw" / "aana-decision-log-skill"


class OpenClawDecisionLogSkillTests(unittest.TestCase):
    def test_manifest_declares_instruction_only_decision_log_boundaries(self):
        manifest = json.loads((SKILL_DIR / "manifest.json").read_text(encoding="utf-8"))

        self.assertEqual(manifest["slug"], "aana-decision-log")
        self.assertFalse(manifest["bundled_code"])
        self.assertFalse(manifest["executes_commands"])
        self.assertFalse(manifest["writes_files"])
        self.assertFalse(manifest["persists_memory"])
        self.assertTrue(manifest["requires_truthful_check_reporting"])
        self.assertTrue(manifest["decision_log_boundary"]["must_log_only_checks_actually_performed"])
        self.assertTrue(manifest["decision_log_boundary"]["must_record_changes_made_after_review"])
        self.assertTrue(manifest["decision_log_boundary"]["may_not_store_raw_private_records"])

    def test_schema_and_example_parse(self):
        schema = json.loads((SKILL_DIR / "schemas" / "decision-log.schema.json").read_text(encoding="utf-8"))
        example = json.loads((SKILL_DIR / "examples" / "redacted-decision-log.json").read_text(encoding="utf-8"))

        for key in schema["required"]:
            self.assertIn(key, example)
        self.assertEqual(example["decision"], "revise")
        self.assertEqual(example["final_action"], "revised")
        self.assertIn("refund approval was not verified", example["failed_checks"])

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
