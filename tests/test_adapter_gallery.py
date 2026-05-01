import importlib.util
import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]


def load_script(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


validate_adapter_gallery = load_script(
    "validate_adapter_gallery", ROOT / "scripts" / "validate_adapter_gallery.py"
)


class AdapterGalleryTests(unittest.TestCase):
    def test_gallery_validates_and_runs_examples(self):
        gallery = validate_adapter_gallery.load_gallery(ROOT / "examples" / "adapter_gallery.json")

        report = validate_adapter_gallery.validate_gallery(gallery, run_examples=True)

        self.assertTrue(report["valid"], report)
        self.assertEqual(report["errors"], 0)
        self.assertGreaterEqual(len(report["checked_examples"]), 3)

    def test_gallery_rejects_missing_adapter_path(self):
        gallery = validate_adapter_gallery.load_gallery(ROOT / "examples" / "adapter_gallery.json")
        broken = dict(gallery)
        broken["adapters"] = [dict(gallery["adapters"][0])]
        broken["adapters"][0]["adapter_path"] = "examples/missing_adapter.json"

        report = validate_adapter_gallery.validate_gallery(broken)

        self.assertFalse(report["valid"])
        self.assertTrue(any("does not exist" in issue["message"] for issue in report["issues"]))


if __name__ == "__main__":
    unittest.main()
