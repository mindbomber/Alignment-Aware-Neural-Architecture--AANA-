import json
import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
SKILL_DIR = ROOT / "examples" / "openclaw" / "aana-continuous-improvement-skill"


class OpenClawContinuousImprovementSkillTests(unittest.TestCase):
    def test_manifest_declares_instruction_only_boundaries(self):
        manifest = json.loads((SKILL_DIR / "manifest.json").read_text(encoding="utf-8"))

        self.assertEqual(manifest["slug"], "aana-continuous-improvement")
        self.assertFalse(manifest["bundled_code"])
        self.assertFalse(manifest["executes_commands"])
        self.assertFalse(manifest["writes_files"])
        self.assertFalse(manifest["persists_memory"])
        self.assertTrue(manifest["requires_user_approval_for_persistence"])
        self.assertTrue(manifest["self_improvement_boundary"]["may_not_modify_system_instructions"])
        self.assertTrue(manifest["self_improvement_boundary"]["may_not_save_memory_without_approval"])

    def test_schema_and_example_parse(self):
        schema = json.loads((SKILL_DIR / "schemas" / "improvement-cycle.schema.json").read_text(encoding="utf-8"))
        example = json.loads((SKILL_DIR / "examples" / "redacted-improvement-cycle.json").read_text(encoding="utf-8"))

        for key in schema["required"]:
            self.assertIn(key, example)
        self.assertEqual(example["risk_level"], "low")
        self.assertEqual(example["allowed_scope"], "current_task_only")

    def test_skill_avoids_executable_patterns(self):
        text = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8").lower()

        blocked_phrases = [
            "python scripts/",
            "pip install",
            "run shell",
            "execute command",
            "save memory without",
        ]
        for phrase in blocked_phrases:
            self.assertNotIn(phrase, text)


if __name__ == "__main__":
    unittest.main()
