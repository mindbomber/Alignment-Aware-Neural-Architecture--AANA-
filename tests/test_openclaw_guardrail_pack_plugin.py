import json
import pathlib
import re
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "examples" / "openclaw" / "aana-guardrail-pack-plugin"
MANIFEST = PLUGIN / "openclaw.plugin.json"
PACKAGE = PLUGIN / "package.json"
EXPECTED_SKILLS = {
    "aana-workflow-readiness-check",
    "aana-task-scope-guardrail",
    "aana-tool-use-gate",
    "aana-human-review-router",
    "aana-private-data-guardrail",
    "aana-file-operation-guardrail",
    "aana-data-export-guardrail",
    "aana-email-send-guardrail",
    "aana-message-send-guardrail",
    "aana-publication-check",
    "aana-evidence-first-answering",
    "aana-code-change-review",
    "aana-decision-log",
}


class OpenClawGuardrailPackPluginTests(unittest.TestCase):
    def test_package_metadata_has_clawhub_required_openclaw_fields(self):
        package = json.loads(PACKAGE.read_text(encoding="utf-8"))

        self.assertEqual(package["name"], "aana-guardrail-pack")
        self.assertEqual(package["version"], "0.1.0")
        self.assertEqual(package["type"], "module")
        self.assertEqual(package["license"], "MIT")
        self.assertNotIn("scripts", package)
        self.assertNotIn("dependencies", package)
        self.assertNotIn("devDependencies", package)
        self.assertEqual(
            package["files"],
            ["openclaw.plugin.json", "README.md", "skills/"],
        )

        openclaw = package["openclaw"]
        self.assertEqual(openclaw["compat"]["pluginApi"], ">=2026.3.24-beta.2")
        self.assertEqual(openclaw["compat"]["minGatewayVersion"], "2026.3.24-beta.2")
        self.assertEqual(openclaw["build"]["openclawVersion"], "2026.3.24-beta.2")
        self.assertEqual(openclaw["build"]["pluginSdkVersion"], "2026.3.24-beta.2")

    def test_plugin_manifest_is_reviewable_no_code_pack(self):
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        documented_fields = {
            "id",
            "name",
            "version",
            "description",
            "skills",
            "configSchema",
        }

        self.assertEqual(manifest["id"], "aana-guardrail-pack")
        self.assertEqual(manifest["skills"], ["skills"])
        self.assertEqual(manifest["configSchema"]["type"], "object")
        self.assertFalse(manifest["configSchema"].get("additionalProperties", True))
        self.assertEqual(set(manifest), documented_fields)

    def test_each_declared_skill_is_bundled_and_instruction_only(self):
        skill_dirs = [path for path in (PLUGIN / "skills").iterdir() if path.is_dir()]
        slug_to_dir = {}

        for skill_dir in skill_dirs:
            skill_manifest_path = skill_dir / "manifest.json"
            self.assertTrue(skill_manifest_path.exists(), skill_dir)
            self.assertTrue((skill_dir / "SKILL.md").exists(), skill_dir)
            skill_manifest = json.loads(skill_manifest_path.read_text(encoding="utf-8"))
            slug_to_dir[skill_manifest["slug"]] = skill_dir
            self.assertEqual(skill_manifest["type"], "instruction_only_skill")
            self.assertFalse(skill_manifest["bundled_code"])
            self.assertFalse(skill_manifest["installs_dependencies"])
            self.assertFalse(skill_manifest["executes_commands"])
            self.assertFalse(skill_manifest["writes_files"])
            self.assertFalse(skill_manifest["writes_event_files"])
            self.assertFalse(skill_manifest["persists_memory"])

        self.assertEqual(EXPECTED_SKILLS, set(slug_to_dir))

    def test_plugin_package_contains_only_text_review_artifacts(self):
        allowed_suffixes = {".json", ".md"}
        files = [path for path in PLUGIN.rglob("*") if path.is_file()]

        self.assertGreater(len(files), 20)
        for path in files:
            self.assertIn(path.suffix.lower(), allowed_suffixes, path)
            self.assertNotIn("__pycache__", path.parts, path)
            self.assertNotEqual(path.suffix.lower(), ".pyc", path)

    def test_plugin_package_avoids_scanner_risky_patterns(self):
        risky_patterns = [
            r"python\s+scripts[/\\]",
            r"\bpip\s+install\b",
            r"\bnpm\s+install\b",
            r"\bexecute\s+(?:a\s+)?(?:local\s+)?(?:command|script|code)\b",
            r"https?://",
            r"raw\.githubusercontent\.com",
            r"\bbit\.ly\b",
            r"\btinyurl\b",
            r"\b\d{1,3}(?:\.\d{1,3}){3}\b",
            r"\bevent[-\s]+files?\b",
            r"\bhelper\s+script\b",
            r"\blocal\s+helper\b",
        ]
        pattern = re.compile("|".join(risky_patterns), re.IGNORECASE)

        for path in PLUGIN.rglob("*"):
            if not path.is_file():
                continue
            text = path.read_text(encoding="utf-8")
            self.assertIsNone(pattern.search(text), path)


if __name__ == "__main__":
    unittest.main()
