import json
import pathlib
import re
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "examples" / "openclaw" / "aana-runtime-connector-plugin"
PACKAGE = PLUGIN / "package.json"
MANIFEST = PLUGIN / "openclaw.plugin.json"
RUNTIME = PLUGIN / "dist" / "index.js"


class OpenClawRuntimeConnectorPluginTests(unittest.TestCase):
    def test_package_metadata_declares_openclaw_extension(self):
        package = json.loads(PACKAGE.read_text(encoding="utf-8"))

        self.assertEqual(package["name"], "aana-runtime-connector")
        self.assertEqual(package["version"], "0.1.0")
        self.assertEqual(package["type"], "module")
        self.assertEqual(package["license"], "MIT")
        self.assertNotIn("scripts", package)
        self.assertNotIn("dependencies", package)
        self.assertNotIn("devDependencies", package)
        self.assertEqual(package["openclaw"]["extensions"], ["./dist/index.js"])
        self.assertEqual(package["openclaw"]["compat"]["pluginApi"], ">=2026.3.24-beta.2")
        self.assertEqual(package["openclaw"]["build"]["openclawVersion"], "2026.3.24-beta.2")

    def test_manifest_has_connector_config_schema(self):
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))

        self.assertEqual(manifest["id"], "aana-runtime-connector")
        self.assertEqual(manifest["version"], "0.1.0")
        schema = manifest["configSchema"]
        self.assertEqual(schema["type"], "object")
        self.assertFalse(schema["additionalProperties"])
        self.assertIn("bridgeBaseUrl", schema["properties"])
        self.assertTrue(schema["properties"]["requireExplicitBridgeBaseUrl"]["default"])

    def test_runtime_registers_expected_optional_tools(self):
        runtime = RUNTIME.read_text(encoding="utf-8")

        self.assertIn('definePluginEntry', runtime)
        for tool_name in (
            "aana_runtime_health",
            "aana_validate_event",
            "aana_agent_check",
            "aana_validate_workflow",
            "aana_workflow_check",
        ):
            self.assertIn(f'name: "{tool_name}"', runtime)

        self.assertEqual(runtime.count("{ optional: true }"), 5)

    def test_runtime_limits_side_effects(self):
        runtime = RUNTIME.read_text(encoding="utf-8")

        allowed_network = ["fetch(endpoint"]
        self.assertIn(allowed_network[0], runtime)
        forbidden = [
            "child_process",
            "exec(",
            "spawn(",
            "writeFile",
            "readFile",
            "appendFile",
            "process.env",
            "localStorage",
            "sessionStorage",
            "registerProvider",
            "registerChannel",
            "registerHook",
            "registerHttpRoute",
            "registerCli",
        ]
        for token in forbidden:
            self.assertNotIn(token, runtime)

    def test_package_files_are_limited_review_artifacts(self):
        allowed_suffixes = {".json", ".md", ".js"}
        files = [path for path in PLUGIN.rglob("*") if path.is_file()]

        self.assertGreater(len(files), 5)
        for path in files:
            self.assertIn(path.suffix.lower(), allowed_suffixes, path)
            self.assertNotIn("__pycache__", path.parts, path)
            self.assertNotEqual(path.suffix.lower(), ".pyc", path)

    def test_package_avoids_install_source_red_flags(self):
        pattern = re.compile(
            "|".join(
                [
                    r"python\s+scripts[/\\]",
                    r"\bpip\s+install\b",
                    r"\bnpm\s+install\b",
                    r"raw\.githubusercontent\.com",
                    r"\bbit\.ly\b",
                    r"\btinyurl\b",
                    r"https?://\d{1,3}(?:\.\d{1,3}){3}",
                ]
            ),
            re.IGNORECASE,
        )

        for path in PLUGIN.rglob("*"):
            if path.is_file():
                self.assertIsNone(pattern.search(path.read_text(encoding="utf-8")), path)


if __name__ == "__main__":
    unittest.main()
