import json
import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
SKILL_DIR = ROOT / "examples" / "openclaw" / "aana-evidence-first-answering-skill"


class OpenClawEvidenceFirstAnsweringSkillTests(unittest.TestCase):
    def test_manifest_declares_instruction_only_evidence_first_boundaries(self):
        manifest = json.loads((SKILL_DIR / "manifest.json").read_text(encoding="utf-8"))

        self.assertEqual(manifest["slug"], "aana-evidence-first-answering")
        self.assertFalse(manifest["bundled_code"])
        self.assertFalse(manifest["executes_commands"])
        self.assertFalse(manifest["writes_files"])
        self.assertFalse(manifest["persists_memory"])
        self.assertTrue(manifest["requires_known_assumed_missing_separation"])
        self.assertTrue(manifest["evidence_first_boundary"]["must_not_treat_assumptions_as_facts"])
        self.assertTrue(manifest["evidence_first_boundary"]["must_name_next_retrieval_steps_for_blocking_gaps"])
        self.assertTrue(manifest["evidence_first_boundary"]["must_revise_unsupported_claims"])

    def test_schema_and_example_parse(self):
        schema = json.loads((SKILL_DIR / "schemas" / "evidence-first-review.schema.json").read_text(encoding="utf-8"))
        example = json.loads((SKILL_DIR / "examples" / "redacted-evidence-first-review.json").read_text(encoding="utf-8"))

        for key in schema["required"]:
            self.assertIn(key, example)
        self.assertEqual(example["recommended_action"], "retrieve")
        self.assertEqual(example["uncertainty_status"], "overconfident")
        self.assertIn("Verified account record", example["missing_evidence"])

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
