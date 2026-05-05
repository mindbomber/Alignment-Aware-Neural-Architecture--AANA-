import json
import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
OPENCLAW = ROOT / "examples" / "openclaw"
EXAMPLES = OPENCLAW / "high-risk-workflow-examples.json"
CONFORMANCE_DOC = ROOT / "docs" / "openclaw-skill-conformance.md"
INSTALL_DOC = ROOT / "docs" / "openclaw-plugin-install-use.md"


class OpenClawSkillConformanceTests(unittest.TestCase):
    def skill_files(self):
        return sorted(OPENCLAW.rglob("SKILL.md"))

    def test_all_skills_include_current_aana_runtime_result_rule(self):
        required_terms = [
            "## AANA Runtime Result Handling",
            "`gate_decision`",
            "`recommended_action`",
            "`aix.hard_blockers`",
            "`candidate_aix`",
            "`aix.score`",
            "revise",
            "ask",
            "defer",
            "refuse",
            "redacted decision metadata",
        ]

        for path in self.skill_files():
            with self.subTest(skill=str(path.relative_to(ROOT))):
                text = path.read_text(encoding="utf-8")
                for term in required_terms:
                    self.assertIn(term, text)

    def test_instruction_only_skills_keep_dependency_boundary(self):
        blocked_phrases = [
            "pip install",
            "npm install",
            "python scripts/",
        ]

        for path in self.skill_files():
            with self.subTest(skill=str(path.relative_to(ROOT))):
                text = path.read_text(encoding="utf-8").lower()
                for phrase in blocked_phrases:
                    self.assertNotIn(phrase, text)

    def test_high_risk_examples_reference_valid_workflow_fixtures(self):
        payload = json.loads(EXAMPLES.read_text(encoding="utf-8"))

        self.assertEqual(payload["version"], "0.1")
        self.assertIn("gate_decision", payload["decision_rule"])
        self.assertGreaterEqual(len(payload["examples"]), 7)
        seen = set()
        for item in payload["examples"]:
            with self.subTest(skill=item.get("skill")):
                self.assertNotIn(item["skill"], seen)
                seen.add(item["skill"])
                self.assertIn("adapter", item)
                self.assertTrue((ROOT / item["workflow_file"]).exists(), item["workflow_file"])
                workflow = json.loads((ROOT / item["workflow_file"]).read_text(encoding="utf-8"))
                self.assertEqual(workflow["adapter"], item["adapter"])
                self.assertTrue(item["required_evidence"])
                for key in ("if_revise", "if_ask", "if_defer", "if_refuse"):
                    self.assertIn(key, item)
                    self.assertTrue(item[key].strip())

    def test_conformance_doc_covers_plugin_and_skill_boundaries(self):
        text = CONFORMANCE_DOC.read_text(encoding="utf-8")

        for phrase in (
            "When To Call AANA",
            "Runtime Result Rule",
            "Audit Boundary",
            "Skill Boundary",
            "High-Risk Examples",
            "Proceed only when `gate_decision` is `pass`",
        ):
            self.assertIn(phrase, text)

    def test_plugin_install_doc_covers_no_code_and_runtime_paths(self):
        text = INSTALL_DOC.read_text(encoding="utf-8")

        for phrase in (
            "aana-guardrail-pack-plugin",
            "aana-runtime-connector-plugin",
            "aana_runtime_ready",
            "aana_workflow_batch",
            "`gate_decision`",
            "`recommended_action`",
            "`aix.hard_blockers`",
        ):
            self.assertIn(phrase, text)


if __name__ == "__main__":
    unittest.main()
