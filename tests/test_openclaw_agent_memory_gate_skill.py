import json
import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
SKILL_DIR = ROOT / "examples" / "openclaw" / "aana-agent-memory-gate-skill"


class OpenClawAgentMemoryGateSkillTests(unittest.TestCase):
    def test_manifest_declares_instruction_only_memory_boundaries(self):
        manifest = json.loads((SKILL_DIR / "manifest.json").read_text(encoding="utf-8"))

        self.assertEqual(manifest["slug"], "aana-agent-memory-gate")
        self.assertFalse(manifest["bundled_code"])
        self.assertFalse(manifest["executes_commands"])
        self.assertFalse(manifest["writes_files"])
        self.assertFalse(manifest["persists_memory"])
        self.assertTrue(manifest["requires_approval_for_memory_storage"])
        self.assertTrue(manifest["requires_approval_for_memory_editing"])
        self.assertTrue(manifest["requires_approval_for_memory_deletion"])
        self.assertTrue(manifest["requires_approval_for_sensitive_memory_reuse"])
        self.assertTrue(manifest["memory_gate_boundary"]["must_require_explicit_approval_before_storing_memory"])
        self.assertTrue(manifest["memory_gate_boundary"]["must_not_treat_silence_as_approval"])
        self.assertTrue(manifest["memory_gate_boundary"]["must_not_reuse_memory_for_unrelated_tasks"])

    def test_schema_and_example_parse(self):
        schema = json.loads((SKILL_DIR / "schemas" / "agent-memory-gate.schema.json").read_text(encoding="utf-8"))
        example = json.loads((SKILL_DIR / "examples" / "redacted-agent-memory-gate.json").read_text(encoding="utf-8"))

        for key in schema["required"]:
            self.assertIn(key, example)
        self.assertEqual(example["memory_operation"], "store")
        self.assertEqual(example["approval_status"], "required")
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
