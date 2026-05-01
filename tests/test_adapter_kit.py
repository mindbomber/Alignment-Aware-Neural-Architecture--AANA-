import importlib.util
import pathlib
import tempfile
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]


def load_script(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


new_adapter = load_script("new_adapter", ROOT / "scripts" / "new_adapter.py")
validate_adapter = load_script("validate_adapter", ROOT / "scripts" / "validate_adapter.py")


class AdapterKitTests(unittest.TestCase):
    def test_scaffold_creates_valid_adapter_package(self):
        with tempfile.TemporaryDirectory() as tmp:
            created = new_adapter.scaffold("Meal Planning", tmp)
            adapter_path = pathlib.Path(created["adapter"])

            self.assertTrue(adapter_path.exists())
            self.assertTrue(pathlib.Path(created["prompt"]).exists())
            self.assertTrue(pathlib.Path(created["bad_candidate"]).exists())
            self.assertTrue(pathlib.Path(created["readme"]).exists())

            adapter = validate_adapter.load_adapter(adapter_path)
            report = validate_adapter.validate_adapter(adapter)

            self.assertTrue(report["valid"], report)
            self.assertGreaterEqual(report["warnings"], 1)
            self.assertEqual(adapter["adapter_name"], "meal_planning_aana_adapter")
            self.assertEqual(adapter["domain"]["name"], "meal_planning")

    def test_travel_adapter_validates(self):
        adapter = validate_adapter.load_adapter(ROOT / "examples" / "travel_adapter.json")

        report = validate_adapter.validate_adapter(adapter)

        self.assertTrue(report["valid"], report)
        self.assertEqual(report["errors"], 0)

    def test_template_reports_placeholders(self):
        adapter = validate_adapter.load_adapter(ROOT / "examples" / "domain_adapter_template.json")

        report = validate_adapter.validate_adapter(adapter)

        self.assertFalse(report["valid"])
        self.assertGreater(report["errors"], 0)
        self.assertTrue(any(issue["level"] == "warning" for issue in report["issues"]))

    def test_duplicate_constraint_ids_fail_validation(self):
        adapter = new_adapter.build_adapter("support triage")
        adapter["constraints"][1]["id"] = adapter["constraints"][0]["id"]

        report = validate_adapter.validate_adapter(adapter)

        self.assertFalse(report["valid"])
        self.assertTrue(
            any("Duplicate constraint id" in issue["message"] for issue in report["issues"])
        )


if __name__ == "__main__":
    unittest.main()
