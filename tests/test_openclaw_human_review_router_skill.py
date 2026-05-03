import json
import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
SKILL_DIR = ROOT / "examples" / "openclaw" / "aana-human-review-router-skill"


class OpenClawHumanReviewRouterSkillTests(unittest.TestCase):
    def test_manifest_declares_instruction_only_human_review_boundaries(self):
        manifest = json.loads((SKILL_DIR / "manifest.json").read_text(encoding="utf-8"))

        self.assertEqual(manifest["slug"], "aana-human-review-router")
        self.assertFalse(manifest["bundled_code"])
        self.assertFalse(manifest["executes_commands"])
        self.assertFalse(manifest["writes_files"])
        self.assertFalse(manifest["persists_memory"])
        self.assertTrue(manifest["requires_review_for_high_impact_actions"])
        self.assertTrue(manifest["human_review_boundary"]["must_route_low_evidence_high_impact_actions"])
        self.assertTrue(manifest["human_review_boundary"]["must_not_treat_silence_as_approval"])
        self.assertTrue(manifest["human_review_boundary"]["must_not_proceed_until_required_review_is_complete"])

    def test_schema_and_example_parse(self):
        schema = json.loads((SKILL_DIR / "schemas" / "human-review-route.schema.json").read_text(encoding="utf-8"))
        example = json.loads((SKILL_DIR / "examples" / "redacted-human-review-route.json").read_text(encoding="utf-8"))

        for key in schema["required"]:
            self.assertIn(key, example)
        self.assertEqual(example["review_route"], "human_review")
        self.assertEqual(example["recommended_action"], "route_to_review")
        self.assertTrue(example["human_review_required"])

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
