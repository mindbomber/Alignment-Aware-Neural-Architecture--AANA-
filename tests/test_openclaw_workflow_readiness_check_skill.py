import json
import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
SKILL_DIR = ROOT / "examples" / "openclaw" / "aana-workflow-readiness-check-skill"


class OpenClawWorkflowReadinessCheckSkillTests(unittest.TestCase):
    def test_manifest_declares_instruction_only_readiness_boundaries(self):
        manifest = json.loads((SKILL_DIR / "manifest.json").read_text(encoding="utf-8"))

        self.assertEqual(manifest["slug"], "aana-workflow-readiness-check")
        self.assertFalse(manifest["bundled_code"])
        self.assertFalse(manifest["executes_commands"])
        self.assertFalse(manifest["writes_files"])
        self.assertFalse(manifest["persists_memory"])
        self.assertTrue(manifest["requires_information_check_before_workflow"])
        self.assertTrue(manifest["requires_permission_check_before_workflow"])
        self.assertTrue(manifest["requires_tool_check_before_workflow"])
        self.assertTrue(manifest["requires_evidence_check_before_workflow"])
        self.assertTrue(manifest["workflow_readiness_boundary"]["must_define_completion_criteria"])
        self.assertTrue(manifest["workflow_readiness_boundary"]["must_not_start_without_required_approval"])
        self.assertTrue(manifest["workflow_readiness_boundary"]["must_route_high_impact_or_irreversible_workflows_to_review"])

    def test_schema_and_example_parse(self):
        schema = json.loads((SKILL_DIR / "schemas" / "workflow-readiness-check.schema.json").read_text(encoding="utf-8"))
        example = json.loads((SKILL_DIR / "examples" / "redacted-workflow-readiness-check.json").read_text(encoding="utf-8"))

        for key in schema["required"]:
            self.assertIn(key, example)
        self.assertEqual(example["readiness_status"], "needs_permission")
        self.assertEqual(example["permission_status"], "required")
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
