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


validator = load_script("validate_verifier_boundaries", ROOT / "scripts" / "validate_verifier_boundaries.py")


class VerifierBoundaryGateTests(unittest.TestCase):
    def test_current_source_defines_tool_reports_only_in_verifier_modules(self):
        self.assertEqual(validator.validate_verifier_boundaries(), [])

    def test_misplaced_tool_report_function_fails_gate(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as temp_dir:
            path = pathlib.Path(temp_dir) / "misplaced.py"
            path.write_text(
                "def accidental_tool_report(prompt, answer):\n"
                "    return {'violations': []}\n",
                encoding="utf-8",
            )

            violations = validator.validate_verifier_boundaries([str(path.relative_to(ROOT))])

        self.assertEqual(len(violations), 1)
        self.assertEqual(violations[0]["name"], "accidental_tool_report")


if __name__ == "__main__":
    unittest.main()
