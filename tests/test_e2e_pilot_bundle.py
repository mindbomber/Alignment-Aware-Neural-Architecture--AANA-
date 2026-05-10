import importlib.util
import io
import pathlib
import tempfile
import unittest
from contextlib import redirect_stdout


ROOT = pathlib.Path(__file__).resolve().parents[1]


def load_script(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


pilot_bundle = load_script("run_e2e_pilot_bundle", ROOT / "scripts" / "pilots" / "run_e2e_pilot_bundle.py")


class E2ePilotBundleTests(unittest.TestCase):
    def test_bundle_runs_selected_events_and_writes_outputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = pathlib.Path(tmp)
            args = pilot_bundle.parse_args(
                [
                    "--event",
                    "support_reply",
                    "--event",
                    "research_summary",
                    "--audit-log",
                    str(tmp_path / "audit" / "pilot.jsonl"),
                    "--metrics-output",
                    str(tmp_path / "metrics" / "pilot-metrics.json"),
                    "--manifest-output",
                    str(tmp_path / "manifests" / "pilot-integrity.json"),
                    "--skip-production-profiles",
                ]
            )

            result = pilot_bundle.run_bundle(args)

            self.assertTrue(result["valid"], result)
            self.assertEqual(result["summary"]["events_checked"], 2)
            self.assertEqual(result["summary"]["event_failures"], 0)
            self.assertEqual(result["summary"]["audit_records"], 2)
            self.assertTrue((tmp_path / "audit" / "pilot.jsonl").exists())
            self.assertTrue((tmp_path / "metrics" / "pilot-metrics.json").exists())
            self.assertTrue((tmp_path / "manifests" / "pilot-integrity.json").exists())
            self.assertEqual(result["release_check"]["summary"]["failures"], 0)
            self.assertEqual(result["production_profiles"]["skipped"], True)

    def test_bundle_marks_failed_expectations_invalid(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = pathlib.Path(tmp)
            event_path = tmp_path / "events"
            event_path.mkdir()
            original = ROOT / "examples" / "agent_events" / "support_reply.json"
            broken = original.read_text(encoding="utf-8").replace(
                '"expected_recommended_action": "revise"',
                '"expected_recommended_action": "accept"',
            )
            (event_path / "support_reply.json").write_text(broken, encoding="utf-8")
            args = pilot_bundle.parse_args(
                [
                    "--events-dir",
                    str(event_path),
                    "--audit-log",
                    str(tmp_path / "pilot.jsonl"),
                    "--skip-production-profiles",
                ]
            )

            result = pilot_bundle.run_bundle(args)

            self.assertFalse(result["valid"])
            self.assertEqual(result["summary"]["event_failures"], 1)
            self.assertFalse(result["events"][0]["passed_expectations"])

    def test_main_returns_zero_for_selected_valid_events(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = io.StringIO()
            with redirect_stdout(output):
                code = pilot_bundle.main(
                    [
                        "--event",
                        "support_reply",
                        "--audit-log",
                        str(pathlib.Path(tmp) / "pilot.jsonl"),
                        "--skip-production-profiles",
                        "--json",
                    ]
                )

            self.assertEqual(code, 0)
            self.assertIn('"valid": true', output.getvalue())


if __name__ == "__main__":
    unittest.main()
